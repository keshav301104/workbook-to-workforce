"""Engine behaviour: error handling, retries, logging, clarification, streaming contract."""
import csv

from flowline.engine import graph

from .conftest import events_of, result_of


def test_transient_api_fault_is_retried(engine, monkeypatch):
    # first attempt fails (0.5 < 1.0), the retry succeeds (0.5 >= 0.3)
    monkeypatch.setattr(graph.random, "random", lambda: 0.5)
    ev, _ = engine.run_to_end("Where is order ORD-1001?", options={"fault_rate": 1.0})
    retries = events_of(ev, "step_retry")
    assert retries and "503" in retries[0]["error"]
    done = {e["step_id"]: e for e in events_of(ev, "step_finished")}
    assert done["search"]["status"] == "ok" and done["search"]["attempts"] == 2
    assert result_of(ev)["status"] == "completed"


def test_persistent_api_fault_fails_the_run_cleanly(engine, monkeypatch):
    monkeypatch.setattr(graph.random, "random", lambda: 0.0)       # every attempt fails
    ev, _ = engine.run_to_end("Where is order ORD-1001?", options={"fault_rate": 1.0})
    r = result_of(ev)
    assert r["status"] == "failed"
    assert "Search order data" in r["sections"][0]["text"] and "503" in r["sections"][0]["text"]
    assert len(events_of(ev, "step_retry")) == 2


def test_missing_file_is_a_clear_failure(engine):
    ev, _ = engine.run_to_end("Which products need restocking?", files=[{"name": "inv.csv", "path": "/nope/inv.csv"}])
    r = result_of(ev)
    assert r["status"] == "failed" and "File not found" in r["sections"][0]["text"]


def test_no_match_and_clarification(engine):
    ev, _ = engine.run_to_end("What's the weather in Miami?")
    assert result_of(ev)["status"] == "no_match"
    ev, _ = engine.run_to_end("show me the products", answers=[{"workflow_id": "WF001"}])
    ask = events_of(ev, "ask")[0]
    assert ask["kind"] == "workflow" and len(ask["options"]) >= 2
    assert result_of(ev)["status"] == "completed"
    assert events_of(ev, "route")[-1]["method"] == "user"


def test_runs_are_logged_step_by_step(engine, settings):
    _, st = engine.run_to_end("Which products need restocking?")
    with settings.live_log_file.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    mine = [r for r in rows if r["run_id"] == st["run_id"]]
    assert {r["workflow_id"] for r in mine} == {"WF001"}
    assert {r["run_status"] for r in mine} == {"success"}
    assert "Load inventory" in {r["step_name"] for r in mine}
    assert settings.history_file.exists()


def test_event_stream_contract(engine):
    ev, _ = engine.run_to_end("Which products need restocking?")
    types = [e["type"] for e in ev]
    assert types[0] == "run_started" and types[-1] == "run_finished"
    for t in ("route", "inputs", "plan", "step_started", "step_finished", "decision", "result"):
        assert t in types
    plan = events_of(ev, "plan")[0]
    assert all(s["excel_text"] for s in plan["steps"])                   # every step shows its Excel origin
    started = [e["step_id"] for e in events_of(ev, "step_started")]
    finished = [e["step_id"] for e in events_of(ev, "step_finished")]
    assert started == finished


def test_resume_reruns_from_the_asked_step_only(engine):
    ev, _ = engine.run_to_end("Where is order ORD-9999?", answers=[{"identifier": "ORD-1002"}])
    assert events_of(ev, "rewind")[0]["to_step"] == "validate"
    assert result_of(ev)["title"] == "Order ORD-1002: Delivered"