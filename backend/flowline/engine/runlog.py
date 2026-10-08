"""Execution logging. Every run writes step-level rows in the same schema as the seeded
history (data/execution_logs.csv), so WF010 reports on the system's own behaviour."""
from __future__ import annotations

import csv
import json
import threading
from datetime import datetime
from typing import Any

from ..config import Settings

LOG_COLUMNS = ["run_id", "timestamp", "workflow_id", "workflow_name", "run_status", "run_duration_ms", "step_id",
               "step_name", "step_status", "step_duration_ms", "error_message", "source"]
STATUS_MAP = {"completed": "success", "escalated": "escalated", "failed": "failed"}
_lock = threading.Lock()


def write_run(settings: Settings, run: dict) -> None:
    status = STATUS_MAP.get(run["status"])
    with _lock:
        if status and run.get("workflow_id"):
            path = settings.live_log_file
            new = not path.exists()
            with path.open("a", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                if new:
                    w.writerow(LOG_COLUMNS)
                for s in run["trace"]:
                    if s.get("kind") == "decision" or s["status"] == "skipped":
                        continue
                    w.writerow([run["run_id"], run["finished_at"], run["workflow_id"], run.get("workflow_name"), status,
                                run["active_ms"], s["id"], s["title"], "failed" if s["status"] == "failed" else "ok",
                                s.get("duration_ms", 0), s.get("error", "") or "", "live"])
        with settings.history_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(run, default=str) + "\n")


def read_history(settings: Settings, limit: int = 100) -> list[dict]:
    if not settings.history_file.exists():
        return []
    rows = []
    with settings.history_file.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return list(reversed(rows))[:limit]


def get_run(settings: Settings, run_id: str) -> dict | None:
    return next((r for r in read_history(settings, 10_000) if r["run_id"] == run_id), None)


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def summary(run: dict) -> dict[str, Any]:
    return {k: run.get(k) for k in ("run_id", "request", "workflow_id", "workflow_name", "status", "active_ms",
                                    "finished_at", "confidence", "route_method", "message")}