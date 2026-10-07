"""Load workflows from the Excel file and join them with their YAML plans.

The Excel file decides WHAT exists (ids, names, triggers, steps, rules, test
requests). Plans decide HOW each step runs, using tools from the registry.
Everything is validated at load time so a broken workflow fails fast with a
clear message instead of halfway through a run.
"""
from __future__ import annotations

import inspect
import re
import threading
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from pydantic import ValidationError

from ..config import Settings, get_settings
from .models import Plan, TestRequest, Workflow, WorkflowSpec

# Tolerant header matching: "Workflow_ID", "workflow id", "Workflow Id" all work.
COLUMN_ALIASES = {
    "id": ["workflow_id", "id", "workflow id"],
    "name": ["workflow_name", "name", "workflow"],
    "trigger": ["trigger", "when"],
    "inputs_text": ["inputs", "input"],
    "steps": ["steps", "step"],
    "decision_logic": ["decision_logic", "decision logic", "rules", "conditions"],
    "tools": ["tools_required", "tools", "tools required"],
    "expected_output": ["expected_output", "expected output", "output"],
}
STEP_SPLIT = re.compile(r"\s*(?:→|->|=>|\n)\s*")


def _norm(s: Any) -> str:
    return re.sub(r"[\s_]+", " ", str(s).strip().lower())


def _map_columns(columns: list[str]) -> dict[str, str]:
    normed = {_norm(c): c for c in columns}
    out = {}
    for key, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            if _norm(a) in normed:
                out[key] = normed[_norm(a)]
                break
    return out


def read_excel_specs(path: Path) -> tuple[list[WorkflowSpec], list[str]]:
    """Parse the workbook. Returns (specs, problems)."""
    problems: list[str] = []
    if not path.exists():
        return [], [f"Workflow file not found: {path}"]
    sheets = pd.read_excel(path, sheet_name=None, dtype=str)
    wf_sheet = next((n for n in sheets if _norm(n) == "workflows"), next(iter(sheets)))
    df = sheets[wf_sheet].fillna("")
    cols = _map_columns(list(df.columns))
    missing = [k for k in ("id", "name", "steps") if k not in cols]
    if missing:
        return [], [f"Sheet '{wf_sheet}' is missing required columns: {', '.join(missing)}"]

    tests: dict[str, list[TestRequest]] = {}
    test_sheet = next((n for n in sheets if "test" in _norm(n)), None)
    if test_sheet:
        tdf = sheets[test_sheet].fillna("")
        tcols = {_norm(c): c for c in tdf.columns}
        idc = tcols.get("workflow id") or tcols.get("id")
        rqc = next((tcols[k] for k in tcols if "request" in k or "question" in k), None)
        chk = next((tcols[k] for k in tcols if "check" in k), None)
        if idc and rqc:
            for _, r in tdf.iterrows():
                if str(r[idc]).strip():
                    tests.setdefault(str(r[idc]).strip(), []).append(
                        TestRequest(request=str(r[rqc]).strip(), check=str(r[chk]).strip() if chk else ""))

    specs, seen = [], set()
    for i, row in df.iterrows():
        get = lambda k: str(row[cols[k]]).strip() if k in cols else ""  # noqa: E731
        wid = get("id")
        if not wid:
            continue
        if wid in seen:
            problems.append(f"Duplicate Workflow_ID '{wid}' in Excel row {i + 2}")
            continue
        seen.add(wid)
        steps = [s for s in STEP_SPLIT.split(get("steps")) if s]
        tools = [t.strip() for t in re.split(r"[;,]", get("tools")) if t.strip()]
        specs.append(WorkflowSpec(
            id=wid, name=get("name"), trigger=get("trigger"), inputs_text=get("inputs_text"), steps=steps,
            decision_logic=get("decision_logic"), tools=tools, expected_output=get("expected_output"),
            test_requests=tests.get(wid, []), excel_row=int(i) + 2,
        ))
    return specs, problems


def _validate_plan(wf: Workflow, tool_registry: dict) -> None:
    plan, spec = wf.plan, wf.spec
    assert plan is not None
    ids = [s.id for s in plan.steps]
    dupes = {x for x in ids if ids.count(x) > 1}
    if dupes:
        wf.issues.append(f"Duplicate step ids: {', '.join(sorted(dupes))}")
    input_names = {i.name for i in plan.inputs}
    covered = set()
    for s in plan.steps:
        for n in s.excel_steps:
            if not 1 <= n <= len(spec.steps):
                wf.issues.append(f"Step '{s.id}' points to Excel step {n}, but the workflow has {len(spec.steps)} steps")
            covered.add(n)
        if s.kind == "tool":
            if not s.tool:
                wf.issues.append(f"Step '{s.id}' has no tool")
                continue
            t = tool_registry.get(s.tool)
            if t is None:
                wf.issues.append(f"Step '{s.id}' uses unknown tool '{s.tool}'")
                continue
            params = t.params
            unknown = [a for a in s.args if a not in params]
            if unknown:
                wf.issues.append(f"Step '{s.id}': tool '{s.tool}' has no argument(s) {', '.join(unknown)}")
            required = [n for n, p in params.items() if p.default is inspect.Parameter.empty]
            absent = [r for r in required if r not in s.args]
            if absent:
                wf.issues.append(f"Step '{s.id}': missing required argument(s) {', '.join(absent)} for '{s.tool}'")
        else:
            if not s.when:
                wf.issues.append(f"Condition step '{s.id}' needs a `when` expression")
            for act in (s.then, s.otherwise):
                if act is None:
                    continue
                if act.goto and act.goto not in ids:
                    wf.issues.append(f"Step '{s.id}' jumps to unknown step '{act.goto}'")
                for f in act.fields:
                    if f not in input_names:
                        wf.issues.append(f"Step '{s.id}' asks for unknown input '{f}'")
    uncovered = [i for i in range(1, len(spec.steps) + 1) if i not in covered]
    for i in uncovered:
        wf.warnings.append(f"Excel step {i} \"{spec.steps[i - 1]}\" is not mapped to any plan step")


def _resolve_params(wf: Workflow) -> None:
    if not wf.plan:
        return
    for name, p in wf.plan.params.items():
        value, source = p.default, "plan default"
        if p.from_excel:
            m = re.search(p.from_excel, wf.spec.decision_logic, re.I)
            if m:
                raw = m.group(1)
                try:
                    value = float(raw) if "." in raw else int(raw)
                except ValueError:
                    value = raw
                source = "Excel decision logic"
            else:
                wf.warnings.append(f"Parameter '{name}' not found in Excel decision logic; using default {p.default}")
        wf.params[name] = value
        wf.param_sources[name] = source


class WorkflowRegistry:
    """Holds the loaded workflows; reloads automatically when Excel or a plan changes."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._lock = threading.Lock()
        self._signature: tuple = ()
        self.workflows: dict[str, Workflow] = {}
        self.problems: list[str] = []
        self.loaded_at: float = 0.0

    def _current_signature(self) -> tuple:
        files = [self.settings.workflow_file, *sorted(self.settings.plans_dir.glob("*.y*ml"))]
        return tuple((str(f), f.stat().st_mtime) for f in files if f.exists())

    def ensure_fresh(self) -> bool:
        sig = self._current_signature()
        if sig != self._signature:
            self.load()
            return True
        return False

    def load(self) -> None:
        with self._lock:
            import time

            specs, problems = read_excel_specs(self.settings.workflow_file)
            plans: dict[str, tuple[Plan, str]] = {}
            for f in sorted(self.settings.plans_dir.glob("*.y*ml")):
                try:
                    raw = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
                    plan = Plan.model_validate(raw)
                    plans[plan.workflow_id] = (plan, f.name)
                except ValidationError as e:
                    first = e.errors()[0]
                    problems.append(f"{f.name}: invalid plan — {'.'.join(map(str, first['loc']))}: {first['msg']}")
                except yaml.YAMLError as e:
                    problems.append(f"{f.name}: YAML error — {e}")
            workflows: dict[str, Workflow] = {}
            for spec in specs:
                wf = Workflow(spec=spec)
                if spec.id in plans:
                    from ..tools import TOOLS  # imported lazily: only needed once plans exist
                    wf.plan, wf.plan_file = plans[spec.id]
                    _validate_plan(wf, TOOLS)
                    _resolve_params(wf)
                else:
                    wf.issues.append("No execution plan yet (add workflows/plans/<id>.yaml or run `python -m flowline compile`)")
                workflows[spec.id] = wf
            for wid in plans:
                if wid not in workflows:
                    problems.append(f"Plan {plans[wid][1]} refers to {wid}, which is not in the Excel file")
            self.workflows, self.problems = workflows, problems
            self._signature = self._current_signature()
            self.loaded_at = time.time()

    def get(self, wid: str) -> Workflow | None:
        self.ensure_fresh()
        return self.workflows.get(wid)

    def all(self) -> list[Workflow]:
        self.ensure_fresh()
        return list(self.workflows.values())


_registry: WorkflowRegistry | None = None


def get_registry() -> WorkflowRegistry:
    global _registry
    if _registry is None:
        _registry = WorkflowRegistry()
        _registry.load()
    return _registry


def reset_registry(settings: Settings | None = None) -> WorkflowRegistry:
    global _registry
    _registry = WorkflowRegistry(settings)
    _registry.load()
    return _registry