"""Run every Excel test question (plus edge cases) and save the transcripts.

    python scripts/generate_examples.py

Writes examples/outputs/<nn>_<workflow>_<slug>.md  (human-readable: selected workflow,
steps executed, decisions, questions asked, final result) and a matching .json with the
full event stream. Uses a temporary runs/ directory so the repo stays clean.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SIM_API_LATENCY_MS", "0")

from flowline import config  # noqa: E402
from flowline.engine import graph  # noqa: E402
from flowline.llm import get_llm  # noqa: E402
from flowline.spec import loader  # noqa: E402

OUT = ROOT / "examples" / "outputs"

SCENARIOS = [
    # (title, request, scripted answers, files, options)
    ("Excel test question", "Which products need restocking?", [], [], {}),
    ("Excel test question", "Find products where vendor price differs by more than 10%.", [], [], {}),
    ("Excel test question (asks for the file)", "Process this vendor spreadsheet and show invalid rows.", [{"vendor_file": "__sample__"}], [], {}),
    ("Excel test question (asks for the product)", "Generate SEO content for this product.", [{"product": "Quilted Liner Vest"}], [], {}),
    ("Excel test question", "Where is order ORD-1001?", [], [], {}),
    ("Excel test question", "Find likely duplicate products in the catalog.", [], [], {}),
    ("Excel test question (asks for goal and dates)", "Create a campaign brief for the new collection.",
     [{"campaign_goal": "drive launch-week sales of the autumn range", "start_date": "2026-10-12", "end_date": "2026-11-02"}], [], {}),
    ("Excel test question (asks for keyword list)", "Classify these keywords and map them to pages.", [{"keyword_file": "__sample__"}], [], {}),
    ("Excel test question (asks for the task)", "Assign this urgent task to the best available developer.",
     [{"task_description": "Fix the checkout payment bug in our React frontend (Stripe), about 6 hours"}], [], {}),
    ("Excel test question", "Which workflows are failing most often?", [], [], {}),
    # edge cases
    ("Edge case: order not found → ask again", "Where is order ORD-9999?",
     [{"identifier": "hello"}, {"identifier": "sofia.reyes@example.com"}], [], {}),
    ("Edge case: threshold overridden from the request", "Flag vendor prices that differ by more than 5%", [], [], {}),
    ("Edge case: product not in catalog, missing attributes", "Write a product description for the Bamboo lounge pants, color: charcoal",
     [{"category": "Loungewear"}], [], {}),
    ("Edge case: end date before start date", "Create a campaign brief for the new collection.",
     [{"campaign_goal": "grow email signups", "start_date": "2026-11-20", "end_date": "2026-11-01"},
      {"start_date": "2026-11-01", "end_date": "2026-11-20"}], [], {}),
    ("Edge case: nobody suitable → escalate", "Urgent: assign a developer. task: rebuild the React checkout with Stripe, 30 hours", [], [], {}),
    ("Edge case: ambiguous request → asks which workflow", "show me the products", [{"workflow_id": "WF001"}], [], {}),
    ("Edge case: out of scope", "What's the weather in Miami?", [], [], {}),
    ("Edge case: simulated API outage → retry", "Where is order ORD-1003?", [], [], {"fault_rate": 1.0}),
]


def fmt_value(v):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.2f}".rstrip("0").rstrip(".")
    return str(v)


def to_markdown(title: str, request: str, events: list[dict]) -> str:
    md = [f"# {title}", "", f"**User request:** “{request}”", ""]
    route = [e for e in events if e["type"] == "route"]
    if route and route[-1].get("workflow_id"):
        r = route[-1]
        md += ["## Selected workflow", f"**{r['workflow_id']} — {r['workflow_name']}** "
               f"(confidence {int(r['confidence'] * 100)}%, {r['method']} router)", "", f"> {r['reasoning']}", ""]
    elif route:
        md += ["## Selected workflow", "None — " + route[-1].get("reasoning", ""), ""]
    inputs = [e for e in events if e["type"] in ("inputs", "input_check")]
    if inputs:
        vals = [f"{i['label']}: `{fmt_value(i['value'])}`" for i in inputs[-1]["inputs"] if i["value"] not in (None, "", [])]
        if vals:
            md += ["**Inputs:** " + " · ".join(vals), ""]
    clar = [e for e in events if e["type"] == "ask" and e.get("kind") == "workflow"]
    if clar:
        first_route = route[0]
        md += [f"_Router was unsure ({int(first_route['confidence'] * 100)}% for {first_route['workflow_id']}), so it asked:_ "
               + clar[0]["message"] + " Options: " + ", ".join(f"{o['id']} {o['name']}" for o in clar[0]["options"]), ""]
    steps = [e for e in events if e["type"] in ("step_finished", "ask", "step_retry", "rewind")]
    if steps:
        md += ["## Steps executed"]
        n = 0
        for e in steps:
            if e["type"] == "ask":
                md.append(f"   - ❓ **Asked the user:** {e['message']}")
                if e.get("options"):
                    md.append("     Options offered: " + ", ".join(f"{o['id']} {o['name']}" for o in e["options"]))
            elif e["type"] == "step_retry":
                md.append(f"   - ↻ retry: {e['error']}")
            elif e["type"] == "rewind":
                md.append(f"   - ↺ resumed from step `{e['to_step']}` with the user's answer")
            else:
                n += 1
                icon = {"ok": "✓", "failed": "✗", "skipped": "–"}[e["status"]]
                tool = "decision" if e["kind"] == "decision" else f"`{e['tool']}`"
                eng = f" · {e['engine']}" if e.get("engine") else ""
                md.append(f"{n}. {icon} **{e['title']}** ({tool}{eng}) — {e.get('summary', '')}")
        md.append("")
    res = [e for e in events if e["type"] == "result"]
    if res:
        r = res[-1]
        md += ["## Result", f"**{r.get('title', '')}** — status: `{r['status']}`", ""]
        if r.get("subtitle"):
            md += [f"_{r['subtitle']}_", ""]
        for s in r["sections"]:
            if s.get("title"):
                md.append(f"**{s['title']}**")
            if s["type"] in ("alert", "summary"):
                md += [f"> {s['text']}", ""]
            elif s["type"] == "kpis":
                md += [" · ".join(f"{k['label']}: **{k['value']}**" for k in s["items"]), ""]
            elif s["type"] == "table":
                if not s["rows"]:
                    md += [f"_{s.get('empty')}_", ""]
                    continue
                cols = s["columns"]
                md.append("| " + " | ".join(c["label"] for c in cols) + " |")
                md.append("|" + "---|" * len(cols))
                for row in s["rows"][:30]:
                    md.append("| " + " | ".join(fmt_value(row.get(c["key"])).replace("|", "/") for c in cols) + " |")
                if s["total"] > 30:
                    md.append(f"\n_…{s['total'] - 30} more rows_")
                md.append("")
            elif s["type"] in ("record", "content"):
                for i in s.get("items") or s.get("fields"):
                    md.append(f"- **{i['label']}:** {i['value']}".replace("\n", " "))
                md.append("")
            elif s["type"] == "list":
                md += [f"- {i}" for i in s["items"]] + [""]
            elif s["type"] == "bars":
                md += [f"- {i['label']}: {i['value']:.1f}%" for i in s["items"]] + [""]
            elif s["type"] == "download":
                md += [f"- 📎 {f['label']} ({f['rows']} rows)" for f in s["files"]] + [""]
    return "\n".join(md)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*"):
        old.unlink()
    with tempfile.TemporaryDirectory() as tmp:
        settings = config.Settings(runs_dir=Path(tmp) / "runs")
        config.set_settings(settings)
        loader.reset_registry(settings)
        graph._engine = None
        engine = graph.get_engine()
        index = ["# Example requests and outputs", "",
                 f"Generated by `python scripts/generate_examples.py` (LLM mode: {get_llm().label}).", "",
                 "| # | Scenario | Request | Workflow | Status |", "|---|---|---|---|---|"]
        for n, (title, req, answers, files, options) in enumerate(SCENARIOS, start=1):
            events, _ = engine.run_to_end(req, answers=answers, files=files, options=options)
            route = [e for e in events if e["type"] == "route"]
            wid = (route[-1].get("workflow_id") if route else None) or "none"
            status = next((e["status"] for e in reversed(events) if e["type"] == "run_finished"), "?")
            slug = re.sub(r"[^a-z0-9]+", "-", req.lower()).strip("-")[:40]
            name = f"{n:02d}_{wid}_{slug}"
            (OUT / f"{name}.md").write_text(to_markdown(title, req, events), encoding="utf-8")
            (OUT / f"{name}.json").write_text(json.dumps(events, indent=1, default=str), encoding="utf-8")
            index.append(f"| {n} | {title} | [{req}]({name}.md) | {wid} | {status} |")
            print(f"{n:02d} {wid:6} {status:10} {req}")
        index += ["", "Notes:", "- In offline mode, LLM steps show the engine `rules` (deterministic fallback). Set an API key in `.env` and re-run to get LLM-written content; the step trace then shows `llm`.",
                  "- WF010 counts the seeded history plus any live runs in `runs/execution_log.csv`, so its numbers differ slightly between machines.",
                  "- Scenario 18 injects simulated API faults, so its retry count varies between runs."]
        (OUT / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()