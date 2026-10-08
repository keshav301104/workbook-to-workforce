"""Turn the user's request into typed workflow inputs.

LLM path: a schema generated from the plan's input definitions (all optional,
"null when not stated" — the model must not guess). Regex/keyword patterns
declared in the plan run as well and fill any gaps, and are the whole story in
offline mode. Values the user did not give stay empty so the engine can ask.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import Field, create_model

from ..expr import _to_date, is_missing
from ..llm import LLMUnavailable
from ..spec.models import InputDef, Plan, Workflow

TYPE_MAP = {"number": Optional[float], "list": Optional[list[str]]}


def normalise(inp: InputDef, value: Any) -> Any:
    if is_missing(value):
        return None
    if inp.type == "number":
        try:
            return float(str(value).replace(",", "").rstrip("%"))
        except ValueError:
            return None
    if inp.type == "date":
        d = _to_date(value)
        return d.isoformat() if d else None
    if inp.type == "list":
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return [p.strip() for p in re.split(r"[\n;,]", str(value)) if p.strip()]
    if inp.type == "choice" and inp.choices:
        v = str(value).strip().lower()
        for c in inp.choices:
            if c.lower() == v or v in [s.lower() for s in inp.synonyms.get(c, [])]:
                return c
        return None
    if isinstance(value, str):
        return value.strip()
    return value


def _pattern_extract(inp: InputDef, text: str) -> Any:
    if inp.type == "choice":
        low = text.lower()
        for c in inp.choices:
            for w in [c, *inp.synonyms.get(c, [])]:
                if re.search(rf"(?<![a-z]){re.escape(w.lower())}(?![a-z])", low):
                    return c
        return None
    for rx in inp.patterns:
        m = re.search(rx, text, re.I | re.S)
        if m:
            return m.group(1) if m.groups() else m.group(0)
    return None


def extract(request: str, wf: Workflow, files: list[dict], llm) -> tuple[dict, dict, str, str | None]:
    """Returns (values, sources, method, note)."""
    plan: Plan = wf.plan  # type: ignore[assignment]
    values: dict[str, Any] = {i.name: None for i in plan.inputs}
    sources: dict[str, str] = {}
    note = None
    method = "patterns"

    # Attached files go to file inputs (first compatible input wins).
    for f in files:
        ext = "." + f["name"].rsplit(".", 1)[-1].lower() if "." in f["name"] else ""
        for inp in plan.inputs:
            if inp.type == "file" and values[inp.name] is None and (not inp.accept or ext in inp.accept):
                values[inp.name] = f["path"]
                sources[inp.name] = "attachment"
                break

    text_inputs = [i for i in plan.inputs if i.type != "file"]
    if llm.enabled and text_inputs:
        try:
            fields = {}
            for i in text_inputs:
                desc = i.description or i.display
                if i.choices:
                    desc += f". One of: {', '.join(i.choices)}"
                if i.type == "date":
                    desc += ". ISO format YYYY-MM-DD"
                fields[i.name] = (TYPE_MAP.get(i.type, Optional[str]), Field(default=None, description=desc))
            schema = create_model("WorkflowInputs", **fields)
            out = llm.structured(
                schema,
                f"Extract the inputs for the '{wf.spec.name}' workflow from the user's request. "
                "Only fill a field when the request explicitly states it (or it is an unambiguous restatement). "
                "Use null for anything not stated. Never guess or use example values. "
                "Phrases like 'this product' or 'these keywords' without the actual content are NOT values.",
                f"Request: {request}",
            ).model_dump()
            for k, v in out.items():
                v = normalise(plan.input(k), v)  # type: ignore[arg-type]
                if v is not None:
                    values[k], sources[k] = v, "request"
            method = "llm"
        except LLMUnavailable as e:
            note = f"LLM extraction unavailable ({e}); used patterns"
    for i in text_inputs:
        if values[i.name] is None:
            v = normalise(i, _pattern_extract(i, request))
            if v is not None:
                values[i.name], sources[i.name] = v, "request"
    return values, sources, method, note


def apply_defaults(wf: Workflow, values: dict, sources: dict) -> None:
    for i in wf.plan.inputs:  # type: ignore[union-attr]
        if is_missing(values.get(i.name)) and i.default is not None:
            values[i.name] = i.default
            sources[i.name] = "default"


def param_overrides(wf: Workflow, request: str) -> tuple[dict, dict]:
    """Decision parameters come from Excel/plan, but the user's request can override them
    (e.g. 'differs by more than 5%')."""
    params, sources = dict(wf.params), dict(wf.param_sources)
    for name, p in (wf.plan.params if wf.plan else {}).items():
        for rx in p.override_patterns:
            m = re.search(rx, request, re.I)
            if m:
                raw = m.group(1)
                try:
                    params[name] = float(raw) if "." in raw else int(raw)
                except ValueError:
                    params[name] = raw
                sources[name] = "request"
                break
    return params, sources