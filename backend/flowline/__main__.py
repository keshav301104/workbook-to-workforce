"""Command line interface.

    python -m flowline serve                      # API on http://127.0.0.1:8000 (frontend: see README)
    python -m flowline run "Which products need restocking?"
    python -m flowline run "Process this vendor file" --file data/vendor_upload_sample.xlsx
    python -m flowline validate                   # check Excel + every plan
    python -m flowline compile WF011              # draft a plan for a new Excel row
    python -m flowline examples                   # regenerate examples/outputs
    python -m flowline tools                      # list the tool library
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

C = {"dim": "\033[2m", "b": "\033[1m", "g": "\033[32m", "y": "\033[33m", "r": "\033[31m", "c": "\033[36m",
     "m": "\033[35m", "x": "\033[0m"}
if not sys.stdout.isatty():
    C = {k: "" for k in C}


def _print_event(e: dict) -> None:
    t = e["type"]
    if t == "run_started":
        print(f"{C['dim']}LLM: {e['llm']}{C['x']}")
    elif t == "route":
        if e.get("workflow_id"):
            print(f"\n{C['b']}Selected workflow:{C['x']} {e['workflow_id']} · {e['workflow_name']} "
                  f"{C['dim']}({int(e['confidence'] * 100)}% · {e['method']}){C['x']}")
            print(f"{C['dim']}  {e['reasoning']}{C['x']}")
        else:
            print(f"\n{C['y']}No workflow matched.{C['x']} {e.get('reasoning', '')}")
    elif t == "inputs":
        vals = {i["label"]: i["value"] for i in e["inputs"] if i["value"] not in (None, "", [])}
        if vals:
            print(f"{C['dim']}Inputs: {json.dumps(vals, default=str)}{C['x']}")
    elif t == "plan":
        print(f"\n{C['b']}Steps executed:{C['x']}")
    elif t == "step_retry":
        print(f"     {C['y']}↻ retry {e['attempt']}/{e['max_attempts'] - 1}: {e['error']}{C['x']}")
    elif t == "step_finished":
        icon = {"ok": f"{C['g']}✓", "failed": f"{C['r']}✗", "skipped": f"{C['dim']}–"}.get(e["status"], "?")
        tag = f" {C['m']}[{e['engine']}]{C['x']}" if e.get("engine") else ""
        print(f"  {icon} {e['title']}{C['x']}{tag} {C['dim']}{e.get('summary', '')} · {e.get('duration_ms', 0)}ms{C['x']}")
    elif t == "decision":
        print(f"     {C['c']}◆ {e['expression']} → {e['result']} → {e['action']}{C['x']}")
    elif t == "result":
        print(f"\n{C['b']}Result: {e.get('title', '')}{C['x']}")
        if e.get("subtitle"):
            print(f"{C['dim']}{e['subtitle']}{C['x']}")
        for s in e.get("sections", []):
            _print_section(s)
    elif t == "error":
        print(f"{C['r']}Error: {e['message']}{C['x']}")


def _print_section(s: dict) -> None:
    title = f"\n  {C['b']}{s['title']}{C['x']}" if s.get("title") else ""
    if s["type"] in ("alert", "summary"):
        print(f"\n  {C['y'] if s.get('tone') in ('warn', 'danger') else C['c']}▌ {s['text']}{C['x']}")
    elif s["type"] == "kpis":
        print("\n  " + "   ".join(f"{i['label']}: {C['b']}{i['value']}{C['x']}" for i in s["items"]))
    elif s["type"] == "table":
        print(title)
        if not s["rows"]:
            print(f"  {C['dim']}{s.get('empty')}{C['x']}")
            return
        cols = s["columns"]
        widths = [min(28, max(len(c["label"]), *(len(str(r.get(c["key"], ""))) for r in s["rows"][:15]))) for c in cols]
        print("  " + "  ".join(c["label"][:w].ljust(w) for c, w in zip(cols, widths)))
        for r in s["rows"][:15]:
            print("  " + "  ".join(str("" if r.get(c["key"]) is None else r.get(c["key"]))[:w].ljust(w) for c, w in zip(cols, widths)))
        if s["total"] > 15:
            print(f"  {C['dim']}… {s['total'] - 15} more rows{C['x']}")
    elif s["type"] in ("record", "content"):
        print(title)
        for i in s.get("items") or s.get("fields") or []:
            print(f"  {C['dim']}{i['label']}:{C['x']} {i['value']}")
    elif s["type"] == "list":
        print(title)
        for i in s["items"]:
            print(f"  • {i}")
    elif s["type"] == "bars":
        print(title)
        mx = max([i["value"] for i in s["items"]] + [1])
        for i in s["items"]:
            print(f"  {i['label'][:28].ljust(28)} {'█' * int(24 * i['value'] / mx)} {i['value']}")
    elif s["type"] == "download":
        for f in s["files"]:
            print(f"\n  ⬇ {f['label']}: runs/exports/…/{f['filename']}")


class NeedsInput(Exception):
    pass


def _prompt(label: str) -> str:
    if not sys.stdin.isatty():
        raise NeedsInput(label)
    try:
        return input(label).strip()
    except EOFError as e:
        raise NeedsInput(label) from e


def _ask(e: dict, scripted: list) -> dict:
    print(f"\n{C['m']}? {e['message']}{C['x']}")
    if e["kind"] == "workflow":
        for n, o in enumerate(e["options"], 1):
            print(f"   {n}. {o['id']} · {o['name']}")
        if scripted:
            return scripted.pop(0)
        while True:
            choice = _prompt("   Choose a number: ")
            if choice.isdigit() and 1 <= int(choice) <= len(e["options"]):
                return {"workflow_id": e["options"][int(choice) - 1]["id"]}
            print("   Enter one of the numbers above.")
    names = [f["name"] for f in e["fields"]]
    if scripted:
        ans = scripted.pop(0)
        unknown = [k for k in ans if k not in names and k != "workflow_id"]
        if unknown:
            print(f"   {C['y']}--answer field(s) {', '.join(unknown)} not asked here; this question needs: {', '.join(names)}{C['x']}")
        return ans
    answers = {}
    for f in e["fields"]:
        hint = " (path, or press Enter for the sample)" if f["type"] == "file" and f.get("sample") else ""
        v = _prompt(f"   {f['label']}{hint}: ")
        answers[f["name"]] = v or ("__sample__" if f["type"] == "file" else v)
    return answers


def cmd_run(args) -> int:
    from .engine import get_engine

    files = []
    for f in args.file or []:
        p = Path(f).resolve()
        if not p.exists():
            print(f"File not found: {f}")
            return 2
        files.append({"name": p.name, "path": str(p)})
    scripted = [json.loads(a) if a.strip().startswith("{") else dict([a.split("=", 1)]) for a in args.answer or []]
    engine = get_engine()
    run_id, events = engine.start(args.request, files, {"fault_rate": args.faults} if args.faults else {})
    status = None
    while True:
        last = None
        for e in events:
            _print_event(e)
            last = e
            if e["type"] == "run_finished":
                status = e["status"]
        if last and last["type"] == "ask":
            try:
                events = engine.resume(run_id, _ask(last, scripted))
            except NeedsInput:
                fields = [f["name"] for f in last.get("fields", [])] or ["workflow_id"]
                print(f"\n{C['y']}Needs input: {', '.join(fields)}. Re-run with --answer {fields[0]}=<value>{C['x']}")
                return 2
            continue
        break
    print(f"\n{C['dim']}Run {run_id} · {status}{C['x']}")
    return 0 if status in ("completed", "escalated") else 1


def cmd_validate(_args) -> int:
    from .spec import get_registry

    reg = get_registry()
    bad = 0
    print(f"{C['b']}{reg.settings.workflow_file.name}{C['x']}: {len(reg.workflows)} workflows\n")
    for p in reg.problems:
        print(f"{C['r']}✗ {p}{C['x']}")
        bad += 1
    for w in reg.workflows.values():
        ok = w.executable
        bad += 0 if ok else 1
        steps = len(w.plan.steps) if w.plan else 0
        print(f"{C['g'] + '✓' if ok else C['r'] + '✗'}{C['x']} {w.id} {w.spec.name:<32} "
              f"{C['dim']}{len(w.spec.steps)} Excel steps → {steps} plan steps · {w.plan_file or 'no plan'}{C['x']}")
        for i in w.issues:
            print(f"    {C['r']}{i}{C['x']}")
        for i in w.warnings:
            print(f"    {C['y']}{i}{C['x']}")
        for k, v in w.params.items():
            print(f"    {C['dim']}param {k} = {v} ({w.param_sources[k]}){C['x']}")
    return 1 if bad else 0


def cmd_compile(args) -> int:
    from .compiler import draft
    from .llm import get_llm
    from .spec import get_registry

    reg = get_registry()
    wf = reg.get(args.workflow_id)
    if not wf:
        print(f"{args.workflow_id} is not in {reg.settings.workflow_file.name}")
        return 2
    text, method, issues = draft(wf.spec, get_llm(), reg.settings.plans_dir / "WF001.yaml")
    out = reg.settings.plans_dir / f"{wf.id}.yaml.draft"
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"{C['b']}Draft written to {out.relative_to(reg.settings.plans_dir.parent.parent)} ({method}){C['x']}")
    for i in issues:
        print(f"  {C['y']}• {i}{C['x']}")
    print(f"Review it, then rename to {wf.id}.yaml — the engine picks it up automatically.")
    return 0


def cmd_tools(_args) -> int:
    from .tools import TOOLS

    for t in sorted(TOOLS.values(), key=lambda t: (t.category, t.name)):
        tags = (" [LLM]" if t.llm else "") + (f" [API: {t.simulated_api}]" if t.simulated_api else "")
        print(f"{C['b']}{t.name:<22}{C['x']} {C['dim']}{t.category:<10}{C['x']} {t.description}{C['m']}{tags}{C['x']}")
    return 0


def cmd_serve(args) -> int:
    import uvicorn

    print(f"Flowline API on http://{args.host}:{args.port}  (docs: /docs). Start the frontend: cd frontend; python -m http.server 5500")
    uvicorn.run("flowline.api:app", host=args.host, port=args.port, reload=args.reload, log_level="warning")
    return 0


def cmd_examples(_args) -> int:
    import runpy

    runpy.run_path(str(Path(__file__).resolve().parent.parent / "scripts" / "generate_examples.py"), run_name="__main__")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="flowline", description="Excel-driven AI workflow agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="start the HTTP API for the frontend")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--reload", action="store_true")
    s.set_defaults(fn=cmd_serve)
    r = sub.add_parser("run", help="run one request in the terminal")
    r.add_argument("request")
    r.add_argument("--file", action="append", help="attach a file (repeatable)")
    r.add_argument("--answer", action="append", help="pre-answer a question: field=value or JSON (repeatable)")
    r.add_argument("--faults", type=float, default=0.0, help="simulated API fault rate 0-1 (to see retries)")
    r.set_defaults(fn=cmd_run)
    v = sub.add_parser("validate", help="validate the Excel file and all plans")
    v.set_defaults(fn=cmd_validate)
    c = sub.add_parser("compile", help="draft a plan for a new Excel workflow")
    c.add_argument("workflow_id")
    c.set_defaults(fn=cmd_compile)
    t = sub.add_parser("tools", help="list available tools")
    t.set_defaults(fn=cmd_tools)
    e = sub.add_parser("examples", help="regenerate examples/outputs")
    e.set_defaults(fn=cmd_examples)
    args = ap.parse_args(argv)
    return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())