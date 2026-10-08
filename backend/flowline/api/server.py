"""HTTP API consumed by the separate frontend.

Runs stream as Server-Sent Events: the browser POSTs a request and reads the
response body as an event stream, so every backend step appears in the UI the
moment it happens. Resuming a paused run is another streaming POST.
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Iterator

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from .. import __version__
from ..compiler import draft
from ..config import get_settings
from ..engine import get_engine
from ..engine import runlog
from ..engine.router import lexical_route
from ..llm import get_llm
from ..spec import get_registry
from ..tools import TOOLS

app = FastAPI(title="Flowline — Excel-driven workflow agent", version=__version__)
# The frontend is a separate app (different port), so the browser needs CORS permission.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    files: list[str] = Field(default_factory=list)      # upload ids
    options: dict[str, Any] = Field(default_factory=dict)


class ResumeRequest(BaseModel):
    value: Any


def _sse(events: Iterator[dict]) -> StreamingResponse:
    def gen():
        for ev in events:
            yield f"data: {json.dumps(ev, default=str)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _upload_path(file_id: str) -> Path | None:
    for p in (get_settings().runs_dir / "uploads").glob(f"{file_id}__*"):
        return p
    return None


@app.get("/")
def root() -> dict:
    return {"service": "flowline-api", "version": __version__, "docs": "/docs", "status": "/api/status"}


@app.get("/api/status")
def status() -> dict:
    reg = get_registry()
    reg.ensure_fresh()
    llm = get_llm()
    wfs = list(reg.workflows.values())
    return {"version": __version__, "llm": llm.label, "llm_enabled": llm.enabled,
            "workflow_file": reg.settings.workflow_file.name, "workflows": len(wfs),
            "executable": sum(w.executable for w in wfs), "problems": reg.problems, "tools": len(TOOLS),
            "router_min_confidence": reg.settings.router_min_confidence, "loaded_at": reg.loaded_at}


def _wf_payload(w) -> dict:
    s = w.spec
    steps = []
    if w.plan:
        for st in w.plan.steps:
            t = TOOLS.get(st.tool or "")
            steps.append({"id": st.id, "title": st.title, "kind": "decision" if st.kind == "condition" else "tool",
                          "tool": st.tool, "category": t.category if t else "decision", "llm": bool(t and t.llm),
                          "api": (st.args.get("api") or t.simulated_api) if t and t.simulated_api else None,
                          "excel_steps": st.excel_steps, "when": st.when, "note": st.note})
    return {
        "id": s.id, "name": s.name, "trigger": s.trigger, "inputs_text": s.inputs_text, "excel_steps": s.steps,
        "decision_logic": s.decision_logic, "tools": s.tools, "expected_output": s.expected_output,
        "test_requests": [t.model_dump() for t in s.test_requests], "excel_row": s.excel_row,
        "plan_file": w.plan_file, "executable": w.executable, "issues": w.issues, "warnings": w.warnings,
        "params": [{"name": k, "value": v, "source": w.param_sources.get(k),
                    "description": w.plan.params[k].description} for k, v in w.params.items()] if w.plan else [],
        "inputs": [{"name": i.name, "label": i.display, "type": i.type, "required": i.required,
                    "default": i.default, "description": i.description} for i in (w.plan.inputs if w.plan else [])],
        "steps": steps,
        "examples": w.plan.examples if w.plan else [],
    }


@app.get("/api/workflows")
def workflows() -> dict:
    reg = get_registry()
    return {"workflows": [_wf_payload(w) for w in reg.all()], "problems": reg.problems,
            "workflow_file": reg.settings.workflow_file.name}


@app.post("/api/workflows/reload")
def reload_workflows() -> dict:
    reg = get_registry()
    reg.load()
    return {"workflows": len(reg.workflows), "executable": sum(w.executable for w in reg.workflows.values()),
            "problems": reg.problems}


@app.post("/api/workflows/{wid}/draft")
def draft_plan(wid: str) -> dict:
    reg = get_registry()
    wf = reg.get(wid)
    if not wf:
        raise HTTPException(404, f"{wid} is not in the Excel file")
    text, method, issues = draft(wf.spec, get_llm(), reg.settings.plans_dir / "WF001.yaml")
    out = reg.settings.plans_dir / f"{wid}.yaml.draft"
    out.write_text(text, encoding="utf-8")
    return {"file": out.name, "method": method, "issues": issues, "yaml": text}


@app.get("/api/route/preview")
def route_preview(q: str = "") -> dict:
    """Instant, LLM-free guess shown while the user types. The real run may still use the LLM router."""
    reg = get_registry()
    if len(q.strip()) < 3:
        return {"workflow_id": None, "workflow_name": None, "confidence": 0.0, "alternatives": []}
    r = lexical_route(q, reg.all())
    return r.as_dict(reg.workflows) | {"threshold": reg.settings.router_min_confidence}


@app.get("/api/tools")
def tools() -> dict:
    return {"tools": [t.describe() for t in TOOLS.values()]}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    name = re.sub(r"[^\w.\- ]+", "_", file.filename or "upload")
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in {"csv", "xlsx", "xls", "tsv", "json", "txt"}:
        raise HTTPException(400, "Upload a CSV, XLSX, TSV or JSON file.")
    fid = uuid.uuid4().hex[:10]
    dest = get_settings().runs_dir / "uploads" / f"{fid}__{name}"
    with dest.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)
    return {"id": fid, "name": name, "size": dest.stat().st_size}


@app.post("/api/runs")
def start_run(req: RunRequest) -> StreamingResponse:
    files = []
    for fid in req.files:
        p = _upload_path(fid)
        if p:
            files.append({"name": p.name.split("__", 1)[-1], "path": str(p)})
    _, events = get_engine().start(req.message, files, req.options)
    return _sse(events)


@app.post("/api/runs/{run_id}/resume")
def resume_run(run_id: str, req: ResumeRequest) -> StreamingResponse:
    value = req.value
    if isinstance(value, dict):  # file answers may reference an upload id
        for k, v in list(value.items()):
            if isinstance(v, str) and v.startswith("upload:"):
                p = _upload_path(v.split(":", 1)[1])
                value[k] = str(p) if p else None
    return _sse(get_engine().resume(run_id, value))


@app.get("/api/runs")
def runs(limit: int = 50) -> dict:
    hist = runlog.read_history(get_settings(), limit)
    return {"runs": [runlog.summary(r) for r in hist]}


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict:
    r = runlog.get_run(get_settings(), run_id)
    if not r:
        raise HTTPException(404, "Run not found")
    return r


@app.get("/api/files/{run_id}/{name}")
def download(run_id: str, name: str) -> FileResponse:
    if not re.fullmatch(r"[\w-]+", run_id) or not re.fullmatch(r"[\w.\-]+", name):
        raise HTTPException(400, "Bad file reference")
    p = get_settings().runs_dir / "exports" / run_id / name
    if not p.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(p, filename=name)


@app.get("/api/samples/{name}")
def sample(name: str) -> FileResponse:
    if not re.fullmatch(r"[\w.\-]+", name):
        raise HTTPException(400, "Bad file name")
    p = get_settings().data_dir / name
    if not p.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(p, filename=name)