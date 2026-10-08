"""HTTP API: status, workflows, streaming runs, resume, uploads, downloads."""
import json

import pytest
from fastapi.testclient import TestClient

from flowline.api import app


@pytest.fixture()
def client(settings):
    return TestClient(app)


def sse(resp):
    return [json.loads(line[6:]) for line in resp.text.splitlines() if line.startswith("data: ")]


def test_status_and_workflows(client):
    s = client.get("/api/status").json()
    assert s["workflows"] == 10 and s["executable"] == 10 and s["llm_enabled"] is False
    wfs = client.get("/api/workflows").json()["workflows"]
    assert wfs[0]["id"] == "WF001" and wfs[0]["steps"][0]["tool"] == "load_table"


def test_streaming_run_and_resume(client):
    ev = sse(client.post("/api/runs", json={"message": "Create a campaign brief for the new collection."}))
    ask = ev[-1]
    assert ask["type"] == "ask"
    ev2 = sse(client.post(f"/api/runs/{ask['run_id']}/resume", json={"value": {
        "campaign_goal": "grow email signups", "start_date": "2026-11-01", "end_date": "2026-11-14"}}))
    assert ev2[-1]["type"] == "run_finished" and ev2[-1]["status"] == "completed"
    runs = client.get("/api/runs").json()["runs"]
    assert runs[0]["run_id"] == ask["run_id"]
    detail = client.get(f"/api/runs/{ask['run_id']}").json()
    assert detail["result"]["title"].startswith("Campaign brief")


def test_upload_then_run_and_download(client, settings):
    data = (settings.data_dir / "vendor_upload_sample.csv").read_bytes()
    up = client.post("/api/upload", files={"file": ("feed.csv", data, "text/csv")}).json()
    ev = sse(client.post("/api/runs", json={"message": "Process this vendor file", "files": [up["id"]]}))
    result = [e for e in ev if e["type"] == "result"][0]
    dl = [s for s in result["sections"] if s["type"] == "download"][0]["files"][0]
    resp = client.get(dl["url"])
    assert resp.status_code == 200 and b"NS-701" in resp.content


def test_upload_rejects_unsupported_types(client):
    r = client.post("/api/upload", files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 400


def test_resume_of_finished_run_is_rejected(client):
    ev = sse(client.post("/api/runs", json={"message": "Which products need restocking?"}))
    rid = ev[0]["run_id"]
    again = sse(client.post(f"/api/runs/{rid}/resume", json={"value": {}}))
    assert again[0]["type"] == "error"