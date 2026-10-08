"""The agent: one generic LangGraph state machine that runs ANY workflow plan.

    route ──► (clarify) ──► extract ──► check_inputs ◄──► ask_inputs
                                            │
                                         prepare ──► step ◄──┐   (one node execution per plan step)
                                                      │ │    │
                                                      │ └► ask_step   (a decision asked the user)
                                                      ▼
                                                   finalize ──► END

Nothing here knows about inventory, orders or keywords. Workflow behaviour lives
in the Excel row + its plan; the graph only interprets plans. Human-in-the-loop
uses LangGraph ``interrupt`` with a checkpointer, so a run pauses, the user
answers in the UI, and the SAME run resumes from where it stopped.

Progress is streamed with ``get_stream_writer`` (stream_mode="custom"): every
routing decision, input, step start/finish, retry, decision and result is an
event the UI renders live.
"""
from __future__ import annotations

import random
import time
import uuid
from typing import Any, Iterator, TypedDict

import pandas as pd
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from ..config import get_settings
from ..expr import ExpressionError, clean, evaluate, is_missing, render, wrap
from ..llm import get_llm
from ..spec import get_registry
from ..spec.models import InputDef, Workflow
from ..tools import TOOLS, ToolContext, ToolError, TransientError
from . import extractor, router, runlog
from .render import render_result

FINAL = {"completed", "escalated", "failed", "no_match", "not_executable", "cancelled"}
CONTEXTS: dict[str, dict[str, Any]] = {}   # run_id -> step outputs (DataFrames stay out of the checkpoint)


class RunState(TypedDict, total=False):
    run_id: str
    request: str
    files: list[dict]
    options: dict
    workflow_id: str | None
    route: dict
    inputs: dict
    input_sources: dict
    params: dict
    param_sources: dict
    pc: int
    status: str
    question: dict | None
    outcome: dict | None
    trace: list[dict]
    timings: dict
    asked: list[str]


# ----------------------------------------------------------------------------- helpers
def _emit(event_type: str, **data: Any) -> None:
    try:
        writer = get_stream_writer()
    except Exception:  # noqa: BLE001  (called outside a streaming run)
        return
    writer({"type": event_type, "ts": time.time(), **data})


def _wf(state: RunState) -> Workflow:
    wf = get_registry().get(state["workflow_id"] or "")
    if wf is None:
        raise RuntimeError(f"Workflow {state['workflow_id']} disappeared from the registry")
    return wf


def _names(state: RunState) -> dict:
    ctx = CONTEXTS.setdefault(state["run_id"], {})
    return {"inputs": wrap(dict(state.get("inputs") or {})), "params": wrap(dict(state.get("params") or {})),
            "request": state.get("request", ""), **ctx}


def preview(value: Any, depth: int = 0) -> Any:
    if isinstance(value, pd.DataFrame):
        cols = [c for c in value.columns if not str(c).startswith("_")][:8]
        rows = [{c: _short(clean(r.get(c))) for c in cols} for r in value.head(5).to_dict("records")]
        return {"kind": "table", "columns": cols, "rows": rows, "total": len(value)}
    if isinstance(value, dict):
        if depth > 0:
            return {"kind": "text", "text": f"{len(value)} fields"}
        return {"kind": "object", "fields": {k: preview(v, depth + 1) for k, v in list(value.items())[:12]}}
    if isinstance(value, (list, tuple)):
        return {"kind": "list", "items": [_short(clean(x)) for x in list(value)[:8]], "total": len(value)}
    return {"kind": "text", "text": _short(clean(value), 400)}


def _short(v: Any, n: int = 80) -> Any:
    if isinstance(v, str) and len(v) > n:
        return v[: n - 1] + "…"
    return v


def _display_inputs(wf: Workflow, values: dict) -> list[dict]:
    out = []
    for i in wf.plan.inputs:  # type: ignore[union-attr]
        v = values.get(i.name)
        if i.type == "file" and v:
            v = str(v).split("/")[-1].split("__", 1)[-1]
        out.append({"name": i.name, "label": i.display, "value": v, "type": i.type, "required": i.required})
    return out


def _field_payload(i: InputDef) -> dict:
    return {"name": i.name, "label": i.display, "type": i.type, "description": i.description, "required": i.required,
            "choices": i.choices, "sample": i.sample, "accept": i.accept, "multiline": i.multiline,
            "placeholder": i.description}


# ----------------------------------------------------------------------------- nodes
def route_node(state: RunState) -> dict:
    t0 = time.perf_counter()
    reg = get_registry()
    reg.ensure_fresh()
    _emit("stage", stage="routing", status="started",
          message=f"Reading {len(reg.workflows)} workflows from {reg.settings.workflow_file.name}")
    workflows = list(reg.workflows.values())
    forced = (state.get("options") or {}).get("workflow_id")
    if forced and forced in reg.workflows:
        result = router.RouteResult(forced, 1.0, "Workflow chosen explicitly.", "manual")
    else:
        result = router.route(state["request"], workflows, get_llm())
    timings = {"route_ms": int((time.perf_counter() - t0) * 1000)}
    payload = result.as_dict(reg.workflows)
    names = {w.id: w.spec.name for w in workflows}
    for a in payload["alternatives"]:
        a["name"] = names.get(a["id"])
    min_conf = get_settings().router_min_confidence
    if result.workflow_id is None:
        status = "no_match"
    elif result.confidence < min_conf:
        status = "clarify"
    elif not reg.workflows[result.workflow_id].executable:
        status = "not_executable"
    else:
        status = "routed"
    _emit("route", **payload, threshold=min_conf, status=status, duration_ms=timings["route_ms"])
    return {"route": payload, "workflow_id": result.workflow_id, "status": status, "timings": timings,
            "trace": [], "inputs": {}, "input_sources": {}, "asked": []}


def clarify_node(state: RunState) -> dict:
    reg = get_registry()
    route = state["route"]
    options = [{"id": route["workflow_id"], "name": route["workflow_name"]}] + route["alternatives"]
    options = [o for o in options if o["id"] and reg.workflows.get(o["id"]) and reg.workflows[o["id"]].executable][:4]
    answer = interrupt({"kind": "workflow", "message": "I'm not sure which workflow you mean. Pick one to continue.",
                        "options": options})
    wid = answer.get("workflow_id") if isinstance(answer, dict) else str(answer)
    if wid not in reg.workflows:
        return {"status": "no_match"}
    route = {**route, "workflow_id": wid, "workflow_name": reg.workflows[wid].spec.name, "method": "user",
             "confidence": 1.0, "reasoning": "Confirmed by the user."}
    _emit("route", **route, status="routed")
    return {"workflow_id": wid, "route": route, "status": "routed"}


def extract_node(state: RunState) -> dict:
    wf = _wf(state)
    t0 = time.perf_counter()
    _emit("stage", stage="extracting", status="started", message="Reading inputs from your request")
    values, sources, method, note = extractor.extract(state["request"], wf, state.get("files") or [], get_llm())
    params, psources = extractor.param_overrides(wf, state["request"])
    ms = int((time.perf_counter() - t0) * 1000)
    _emit("inputs", inputs=_display_inputs(wf, values), sources=sources, method=method, note=note, duration_ms=ms)
    _emit("params", params=[{"name": k, "value": v, "source": psources.get(k),
                             "description": wf.plan.params[k].description} for k, v in params.items()])
    return {"inputs": values, "input_sources": sources, "params": params, "param_sources": psources,
            "timings": {**state.get("timings", {}), "extract_ms": ms}}


def check_inputs_node(state: RunState) -> dict:
    wf = _wf(state)
    values, sources = dict(state["inputs"]), dict(state["input_sources"])
    extractor.apply_defaults(wf, values, sources)
    missing = [i for i in wf.plan.inputs if i.required and is_missing(values.get(i.name))]  # type: ignore[union-attr]
    _emit("input_check", ok=not missing, missing=[i.name for i in missing],
          inputs=_display_inputs(wf, values), sources=sources)
    if missing:
        msg = " ".join(i.ask or f"Please provide {i.display.lower()}." for i in missing)
        return {"inputs": values, "input_sources": sources, "status": "needs_input",
                "question": {"kind": "inputs", "message": msg, "fields": [_field_payload(i) for i in missing],
                             "workflow_id": wf.id}}
    return {"inputs": values, "input_sources": sources, "status": "inputs_ok", "question": None}


def _merge_answers(wf: Workflow, state: RunState, answers: Any) -> tuple[dict, dict]:
    values, sources = dict(state["inputs"]), dict(state["input_sources"])
    if not isinstance(answers, dict):
        answers = {}
    for k, v in answers.items():
        inp = wf.plan.input(k)  # type: ignore[union-attr]
        if inp is None:
            continue
        if inp.type == "file" and v == "__sample__" and inp.sample:
            v = inp.sample
        v = extractor.normalise(inp, v)
        if v is not None:
            values[k], sources[k] = v, "you"
    # Answers often carry extra details ("...about 6 hours, by Friday"): run the plan's
    # patterns over the answer text to fill other inputs that are still empty.
    text = " ".join(str(v) for v in answers.values() if isinstance(v, str) and not v.startswith("__"))
    if text:
        for inp in wf.plan.inputs:  # type: ignore[union-attr]
            if inp.type != "file" and is_missing(values.get(inp.name)) or sources.get(inp.name) == "default":
                if inp.type == "file" or inp.name in answers:
                    continue
                v = extractor.normalise(inp, extractor._pattern_extract(inp, text))
                if v is not None:
                    values[inp.name], sources[inp.name] = v, "you"
    return values, sources


def ask_inputs_node(state: RunState) -> dict:
    wf = _wf(state)
    answers = interrupt(state["question"])
    values, sources = _merge_answers(wf, state, answers)
    _emit("inputs", inputs=_display_inputs(wf, values), sources=sources, method="user")
    return {"inputs": values, "input_sources": sources, "question": None,
            "asked": [*state.get("asked", []), *[k for k in (answers or {})]]}


def prepare_node(state: RunState) -> dict:
    wf = _wf(state)
    CONTEXTS[state["run_id"]] = {}
    steps = []
    for s in wf.plan.steps:  # type: ignore[union-attr]
        t = TOOLS.get(s.tool or "")
        steps.append({"id": s.id, "title": s.title, "kind": "decision" if s.kind == "condition" else "tool",
                      "tool": s.tool, "category": t.category if t else "decision", "llm": bool(t and t.llm),
                      "api": (s.args.get("api") or t.simulated_api) if t and t.simulated_api else None,
                      "excel_steps": s.excel_steps,
                      "excel_text": [wf.spec.steps[n - 1] for n in s.excel_steps if 1 <= n <= len(wf.spec.steps)],
                      "note": s.note})
    _emit("plan", workflow_id=wf.id, workflow_name=wf.spec.name, steps=steps,
          excel_steps=wf.spec.steps, decision_logic=wf.spec.decision_logic, plan_file=wf.plan_file)
    _emit("stage", stage="executing", status="started", message=f"Running {len(steps)} steps")
    return {"pc": 0, "status": "running", "trace": []}


def _simulate_api(api: str, attempt: int, options: dict) -> None:
    """Simulated external API: realistic latency, and optional injected faults to
    demonstrate retries (first attempt fails with `fault_rate`, later ones with 30% of it)."""
    settings = get_settings()
    time.sleep(settings.api_latency_ms / 1000 * random.uniform(0.6, 1.4))
    rate = float(options.get("fault_rate", settings.fault_rate) or 0)
    if rate and random.random() < (rate if attempt == 1 else rate * 0.3):
        raise TransientError(f"{api} returned 503 Service Unavailable (simulated fault)")


def step_node(state: RunState) -> dict:
    wf = _wf(state)
    plan = wf.plan
    pc = state["pc"]
    step = plan.steps[pc]  # type: ignore[union-attr]
    names = _names(state)
    trace = list(state.get("trace", []))
    entry: dict[str, Any] = {"id": step.id, "title": step.title, "kind": "decision" if step.kind == "condition" else "tool",
                             "tool": step.tool, "excel_steps": step.excel_steps, "logs": []}
    t0 = time.perf_counter()

    def finish(status: str, **extra: Any) -> None:
        entry.update(status=status, duration_ms=int((time.perf_counter() - t0) * 1000), **extra)
        trace.append(entry)
        _emit("step_finished", step_id=step.id, **{k: v for k, v in entry.items() if k not in ("id", "logs")})

    _emit("step_started", step_id=step.id, title=step.title, tool=step.tool, kind=entry["kind"])

    # ---------------------------------------------------------------- decision step
    if step.kind == "condition":
        try:
            truth = bool(evaluate(step.when, names))  # type: ignore[arg-type]
        except ExpressionError as e:
            finish("failed", error=str(e), summary="Could not evaluate decision")
            return {"trace": trace, "status": "failed", "outcome": {"status": "failed", "message": str(e), "step": step.id}}
        action = (step.then if truth else step.otherwise)
        act = action.action if action else "continue"
        message = render(action.message, names) if action and action.message else None
        _emit("decision", step_id=step.id, expression=step.when, result=truth, action=act, message=message,
              note=step.note)
        finish("ok", summary=f"`{step.when}` → {'true' if truth else 'false'} → {act}", result=truth, action=act,
               message=message)
        nxt = pc + 1
        if act == "continue":
            return {"trace": trace, "pc": nxt, "status": "running" if nxt < len(plan.steps) else "completed"}  # type: ignore[union-attr]
        if act == "goto":
            return {"trace": trace, "pc": plan.step_index(action.goto), "status": "running"}  # type: ignore[union-attr]
        if act in ("complete", "escalate", "fail"):
            status = {"complete": "completed", "escalate": "escalated", "fail": "failed"}[act]
            return {"trace": trace, "status": status, "outcome": {"status": status, "message": message, "step": step.id}}
        if act == "ask":
            values = dict(state["inputs"])
            for f in action.clear:  # type: ignore[union-attr]
                values[f] = None
            q = {"kind": "step", "message": message or "More information is needed.", "step_id": step.id,
                 "fields": [_field_payload(plan.input(f)) for f in action.fields],  # type: ignore[union-attr]
                 "goto": action.goto or step.id, "workflow_id": wf.id}  # type: ignore[union-attr]
            return {"trace": trace, "status": "asking", "question": q, "inputs": values}

    # ---------------------------------------------------------------- tool step
    if step.when is not None:
        try:
            run_it = bool(evaluate(step.when, names))
        except ExpressionError:
            run_it = False
        if not run_it:
            finish("skipped", summary=f"Skipped: `{step.when}` is false")
            nxt = pc + 1
            return {"trace": trace, "pc": nxt, "status": "running" if nxt < len(plan.steps) else "completed"}  # type: ignore[union-attr]

    spec = TOOLS[step.tool]  # type: ignore[index]
    max_attempts = 1 + max(step.retry, 2 if spec.simulated_api else 0)
    settings = get_settings()
    options = state.get("options") or {}

    def emit_log(ev: dict) -> None:
        entry["logs"].append({"message": ev["message"], "level": ev.get("level", "info")})
        _emit(ev["type"], **{k: v for k, v in ev.items() if k != "type"})

    error, result = None, None
    for attempt in range(1, max_attempts + 1):
        try:
            args = {k: (v if k in spec.raw_args else render(v, names)) for k, v in step.args.items()}
            ctx = ToolContext(settings, get_llm(), state["run_id"], step.id, names, emit_log)
            if spec.simulated_api:
                api = args.pop("api", None) or spec.simulated_api
                emit_log({"type": "step_log", "step_id": step.id, "message": f"Calling {api}…", "level": "info"})
                _simulate_api(api, attempt, options)
            result = spec.fn(ctx, **args)
            error = None
            entry["attempts"] = attempt
            break
        except TransientError as e:
            error = str(e)
            if attempt < max_attempts:
                backoff = round(0.4 * 2 ** (attempt - 1), 2)
                _emit("step_retry", step_id=step.id, attempt=attempt, max_attempts=max_attempts, error=error,
                      backoff_s=backoff)
                entry["logs"].append({"message": f"Attempt {attempt} failed: {error}. Retrying in {backoff}s", "level": "warn"})
                time.sleep(backoff)
        except (ToolError, ExpressionError) as e:
            error = str(e)
            break
        except Exception as e:  # noqa: BLE001  (unexpected bug in a tool -> fail the step, not the server)
            error = f"{type(e).__name__}: {e}"
            break

    nxt = pc + 1
    if error is None and result is not None:
        if step.output:
            CONTEXTS.setdefault(state["run_id"], {})[step.output] = wrap(result.value)
        finish("ok", summary=result.summary, engine=result.engine, output=step.output, preview=preview(result.value))
        return {"trace": trace, "pc": nxt, "status": "running" if nxt < len(plan.steps) else "completed"}  # type: ignore[union-attr]

    if step.on_error == "continue":
        finish("failed", error=error, summary=f"Failed but continuing: {error}", continued=True)
        return {"trace": trace, "pc": nxt, "status": "running" if nxt < len(plan.steps) else "completed"}  # type: ignore[union-attr]
    finish("failed", error=error, summary=error)
    return {"trace": trace, "status": "failed", "outcome": {"status": "failed", "step": step.id,
                                                             "message": f"Step “{step.title}” failed: {error}"}}


def ask_step_node(state: RunState) -> dict:
    wf = _wf(state)
    q = state["question"]
    answers = interrupt(q)
    values, sources = _merge_answers(wf, state, answers)
    goto = wf.plan.step_index(q["goto"])  # type: ignore[union-attr]
    _emit("inputs", inputs=_display_inputs(wf, values), sources=sources, method="user")
    _emit("rewind", to_step=q["goto"], message="Re-running from this step with your answer")
    # drop trace entries from the rewound part so timings and logs stay honest
    ids_after = {s.id for s in wf.plan.steps[goto:]}  # type: ignore[union-attr]
    trace = [t for t in state.get("trace", []) if t["id"] not in ids_after]
    return {"inputs": values, "input_sources": sources, "pc": goto, "status": "running", "question": None,
            "trace": trace}


def finalize_node(state: RunState) -> dict:
    reg = get_registry()
    status = state.get("status")
    if status in ("running", "inputs_ok", "routed"):
        status = "completed"
    outcome = state.get("outcome") or {}
    wf = reg.workflows.get(state.get("workflow_id") or "")
    result: dict[str, Any]
    if status == "no_match":
        names_list = ", ".join(f"{w.spec.name}" for w in reg.workflows.values())
        result = {"title": "No matching workflow", "sections": [
            {"type": "alert", "tone": "info", "text": "This request doesn't match any configured workflow. "
                                                       "Try rephrasing it, or pick one of: " + names_list + "."}]}
    elif status == "not_executable":
        result = {"title": f"{wf.spec.name} isn't runnable yet" if wf else "Workflow not runnable",
                  "sections": [{"type": "alert", "tone": "warn", "text": "; ".join(wf.issues) if wf else ""}]}
    else:
        names = _names(state)
        names["outcome"] = wrap(outcome)
        names["status"] = status
        result = render_result(wf.plan.result, names) if wf and wf.plan else {"title": "", "sections": []}
        if outcome.get("message"):
            tone = {"escalated": "warn", "failed": "danger"}.get(status, "info")
            result["sections"].insert(0, {"type": "alert", "tone": tone, "text": outcome["message"],
                                          "title": {"escalated": "Escalated", "failed": "Run failed"}.get(status)})
    trace = state.get("trace", [])
    timings = state.get("timings", {})
    active = timings.get("route_ms", 0) + timings.get("extract_ms", 0) + sum(t.get("duration_ms", 0) for t in trace)
    run = {"run_id": state["run_id"], "request": state["request"], "workflow_id": state.get("workflow_id"),
           "workflow_name": wf.spec.name if wf else None, "status": status, "active_ms": active,
           "finished_at": runlog.now(), "confidence": (state.get("route") or {}).get("confidence"),
           "route_method": (state.get("route") or {}).get("method"), "message": outcome.get("message"),
           "inputs": {k: (str(v).split("/")[-1] if isinstance(v, str) and "/" in v else v)
                      for k, v in (state.get("inputs") or {}).items()},
           "trace": [{k: v for k, v in t.items() if k != "preview"} for t in trace], "result": result}
    try:
        runlog.write_run(get_settings(), run)
    except OSError as e:
        _emit("warning", message=f"Could not write run log: {e}")
    _emit("result", status=status, **result)
    _emit("run_finished", status=status, active_ms=active, workflow_id=state.get("workflow_id"))
    CONTEXTS.pop(state["run_id"], None)
    return {"status": status}


# ----------------------------------------------------------------------------- wiring
def _after_route(state: RunState) -> str:
    return {"routed": "extract", "clarify": "clarify"}.get(state["status"], "finalize")


def _after_clarify(state: RunState) -> str:
    return "extract" if state["status"] == "routed" else "finalize"


def _after_check(state: RunState) -> str:
    return "ask_inputs" if state["status"] == "needs_input" else "prepare"


def _after_step(state: RunState) -> str:
    s = state["status"]
    if s == "running":
        return "step"
    if s == "asking":
        return "ask_step"
    return "finalize"


def build_graph():
    g = StateGraph(RunState)
    g.add_node("route", route_node)
    g.add_node("clarify", clarify_node)
    g.add_node("extract", extract_node)
    g.add_node("check_inputs", check_inputs_node)
    g.add_node("ask_inputs", ask_inputs_node)
    g.add_node("prepare", prepare_node)
    g.add_node("step", step_node)
    g.add_node("ask_step", ask_step_node)
    g.add_node("finalize", finalize_node)
    g.add_edge(START, "route")
    g.add_conditional_edges("route", _after_route, ["extract", "clarify", "finalize"])
    g.add_conditional_edges("clarify", _after_clarify, ["extract", "finalize"])
    g.add_edge("extract", "check_inputs")
    g.add_conditional_edges("check_inputs", _after_check, ["ask_inputs", "prepare"])
    g.add_edge("ask_inputs", "check_inputs")
    g.add_edge("prepare", "step")
    g.add_conditional_edges("step", _after_step, ["step", "ask_step", "finalize"])
    g.add_edge("ask_step", "step")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=InMemorySaver())


class Engine:
    """Thin facade used by the API, CLI and tests."""

    def __init__(self) -> None:
        self.graph = build_graph()
        self.active: dict[str, dict] = {}

    def _config(self, run_id: str) -> dict:
        return {"configurable": {"thread_id": run_id}, "recursion_limit": 400}

    def _stream(self, run_id: str, payload: Any) -> Iterator[dict]:
        try:
            for mode, chunk in self.graph.stream(payload, self._config(run_id), stream_mode=["custom", "updates"]):
                if mode == "custom":
                    chunk["run_id"] = run_id
                    yield chunk
                elif mode == "updates" and "__interrupt__" in chunk:
                    for intr in chunk["__interrupt__"]:
                        self.active[run_id] = {"waiting": True, "question": intr.value}
                        yield {"type": "ask", "run_id": run_id, "ts": time.time(), **intr.value}
        except Exception as e:  # noqa: BLE001
            yield {"type": "error", "run_id": run_id, "ts": time.time(), "message": f"{type(e).__name__}: {e}"}
            yield {"type": "run_finished", "run_id": run_id, "ts": time.time(), "status": "failed"}

    def start(self, request: str, files: list[dict] | None = None, options: dict | None = None,
              run_id: str | None = None) -> tuple[str, Iterator[dict]]:
        run_id = run_id or uuid.uuid4().hex[:12]
        self.active[run_id] = {"waiting": False}
        init: RunState = {"run_id": run_id, "request": request.strip(), "files": files or [], "options": options or {}}

        def gen() -> Iterator[dict]:
            yield {"type": "run_started", "run_id": run_id, "ts": time.time(), "request": request,
                   "llm": get_llm().label, "llm_enabled": get_llm().enabled}
            yield from self._stream(run_id, init)

        return run_id, gen()

    def resume(self, run_id: str, answer: Any) -> Iterator[dict]:
        snap = self.graph.get_state(self._config(run_id))
        if not snap or not snap.next:
            yield {"type": "error", "run_id": run_id, "ts": time.time(), "message": "This run is not waiting for input."}
            return
        self.active[run_id] = {"waiting": False}
        yield {"type": "resumed", "run_id": run_id, "ts": time.time()}
        yield from self._stream(run_id, Command(resume=answer))

    def state(self, run_id: str) -> dict:
        snap = self.graph.get_state(self._config(run_id))
        return dict(snap.values) if snap else {}

    def run_to_end(self, request: str, answers: list[Any] | None = None, files: list[dict] | None = None,
                   options: dict | None = None) -> tuple[list[dict], dict]:
        """Synchronous helper (tests / examples): answers are fed to each successive question."""
        answers = list(answers or [])
        run_id, it = self.start(request, files, options)
        events = list(it)
        while events and events[-1]["type"] == "ask":
            if not answers:
                break
            events += list(self.resume(run_id, answers.pop(0)))
        return events, self.state(run_id)


_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = Engine()
    return _engine