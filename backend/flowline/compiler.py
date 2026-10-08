"""Draft an execution plan for a NEW Excel workflow row (the "11th workflow" path).

    python -m flowline compile WF011

With an LLM: the model gets the Excel row, the tool catalogue (names, args,
descriptions) and an existing plan as a style reference, and writes YAML. The
draft is validated with the same checks the loader uses (tool names, argument
names, step coverage); validation errors are fed back once for a repair pass.

Offline: a skeleton is produced — one plan step per Excel step with the closest
matching tool and TODO arguments — so a developer only fills in the blanks.

Drafts are written as ``workflows/plans/<ID>.yaml.draft`` and are NOT loaded
until a human reviews them and renames the file to ``<ID>.yaml``.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import ValidationError
from rapidfuzz import fuzz

from .llm import LLMUnavailable
from .spec.loader import _validate_plan
from .spec.models import Plan, Workflow, WorkflowSpec
from .tools import TOOLS

DSL_GUIDE = """Plan YAML format:
workflow_id: <ID>
description: <one line>
examples: [<extra example requests>]
params: {<name>: {default: <value>, description: <text>, from_excel: '<regex with 1 group to read the value from Decision_Logic>'}}
inputs: [{name, type: text|number|file|date|list|identifier|choice, label, description, required: bool, default, ask, patterns: ['<regex>']}]
steps:
  - {id, title, excel_step: <1-based index or list>, tool: <tool name>, args: {...}, output: <variable name>}
  - {id, title, excel_step, kind: condition, when: '<expression>', then: {action: continue|complete|ask|escalate|fail|goto, message, fields: [<inputs>], goto: <step id>}}
result: {title: '<template>', subtitle: '<template>', sections: [{type: kpis|table|content|record|alert|list|bars|download, ...}]}
References: "$var.field" passes an object; "{{ expression }}" evaluates (functions: len, count(table, 'row expr'), where(table, 'row expr'), first, col, unique, join, pct, money, exists, missing, round...).
Row expressions (filter_rows.where, compute_column.columns, flag_rows.when) see the row's columns plus inputs.*, params.*.
Data files available: products.csv (sku, product_name, category, internal_price, unit_cost, ...), inventory.csv, vendor_prices.csv, orders.csv, shipments.csv, catalog.csv, keywords.csv, categories.csv, employees.csv, execution_logs.csv."""


def tool_catalogue() -> str:
    lines = []
    for t in TOOLS.values():
        d = t.describe()
        args = ", ".join(f"{k} ({v})" for k, v in d["args"].items())
        lines.append(f"- {t.name}: {t.description} Args: {args}")
    return "\n".join(lines)


def _snake(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:40] or "input"


def _check(text: str, spec: WorkflowSpec) -> tuple[Plan | None, list[str]]:
    try:
        raw = yaml.safe_load(text)
        plan = Plan.model_validate(raw)
    except (yaml.YAMLError, ValidationError) as e:
        return None, [f"Plan does not parse: {str(e)[:400]}"]
    if plan.workflow_id != spec.id:
        return None, [f"workflow_id must be {spec.id}"]
    wf = Workflow(spec=spec, plan=plan)
    _validate_plan(wf, TOOLS)
    return plan, wf.issues + wf.warnings


def skeleton(spec: WorkflowSpec) -> str:
    inputs = []
    for part in [p.strip() for p in re.split(r"[;,]", spec.inputs_text) if p.strip()]:
        is_file = bool(re.search(r"csv|xlsx|file|list|catalog|logs?|data", part, re.I))
        inputs.append({"name": _snake(part), "type": "file" if is_file else "text", "label": part,
                       "description": part, "required": not is_file})
    steps = []
    for i, text in enumerate(spec.steps, start=1):
        best = max(TOOLS.values(), key=lambda t: fuzz.token_set_ratio(text.lower(), f"{t.name.replace('_', ' ')} {t.description}".lower()))
        required = [n for n, p in best.params.items() if p.default is p.empty]
        steps.append({"id": f"s{i}", "title": text[0].upper() + text[1:], "excel_step": i, "tool": best.name,
                      "args": {a: "TODO" for a in required}, "output": f"step{i}"})
    plan = {"workflow_id": spec.id, "description": spec.name, "inputs": inputs, "steps": steps,
            "result": {"title": spec.name, "sections": [{"type": "table", "title": spec.expected_output,
                                                          "data": f"$step{len(steps)}"}]}}
    header = (f"# DRAFT plan for {spec.id} — {spec.name} (offline skeleton).\n"
              f"# Each Excel step is mapped to the closest tool; replace every TODO, then rename to {spec.id}.yaml\n")
    return header + yaml.safe_dump(plan, sort_keys=False, allow_unicode=True, width=120)


def draft(spec: WorkflowSpec, llm, example_plan: Path | None) -> tuple[str, str, list[str]]:
    """Returns (yaml_text, method, issues)."""
    if llm.enabled:
        example = example_plan.read_text(encoding="utf-8") if example_plan and example_plan.exists() else ""
        system = ("You write execution plans for a workflow engine. Output ONLY a YAML document in a ```yaml block.\n"
                  f"{DSL_GUIDE}\n\nAvailable tools:\n{tool_catalogue()}\n\nExample plan:\n```yaml\n{example}\n```")
        row = (f"Workflow_ID: {spec.id}\nName: {spec.name}\nTrigger: {spec.trigger}\nInputs: {spec.inputs_text}\n"
               f"Steps: {' → '.join(spec.steps)}\nDecision_Logic: {spec.decision_logic}\n"
               f"Tools_Required: {', '.join(spec.tools)}\nExpected_Output: {spec.expected_output}")
        prompt = f"Write the plan for this Excel row. Map every Excel step (excel_step).\n\n{row}"
        try:
            for attempt in range(2):
                out = llm.text(system, prompt)
                m = re.search(r"```(?:yaml)?\s*(.+?)```", out, re.S)
                text = (m.group(1) if m else out).strip()
                _, issues = _check(text, spec)
                if not issues:
                    return f"# DRAFT plan for {spec.id}, written by the LLM. Review, then rename to {spec.id}.yaml\n{text}\n", "llm", []
                prompt += f"\n\nYour previous draft had these problems, fix them:\n- " + "\n- ".join(issues) + f"\n\nPrevious draft:\n{text}"
            return f"# DRAFT plan for {spec.id} (LLM, needs fixes)\n{text}\n", "llm", issues
        except LLMUnavailable:
            pass
    text = skeleton(spec)
    _, issues = _check(text, spec)
    return text, "skeleton", issues