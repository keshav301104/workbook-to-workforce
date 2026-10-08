import os
import sys
from pathlib import Path

# Tests are deterministic: offline LLM mode and no simulated latency.
os.environ["LLM_PROVIDER"] = "offline"
os.environ["SIM_API_LATENCY_MS"] = "0"
os.environ["SIM_FAULT_RATE"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from flowline import config  # noqa: E402
from flowline.engine import graph  # noqa: E402
from flowline.llm import client as llm_client  # noqa: E402
from flowline.spec import loader  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _fresh(settings):
    config.set_settings(settings)
    llm_client._client = None
    graph._engine = None
    return loader.reset_registry(settings)


@pytest.fixture()
def settings(tmp_path):
    s = config.Settings(runs_dir=tmp_path / "runs")
    _fresh(s)
    yield s


@pytest.fixture()
def engine(settings):
    return graph.get_engine()


def events_of(events, kind):
    return [e for e in events if e["type"] == kind]


def result_of(events):
    r = events_of(events, "result")
    assert r, f"no result event; last events: {[e['type'] for e in events[-5:]]}"
    return r[-1]


def section(result, title=None, type_=None):
    for s in result["sections"]:
        if (title is None or s.get("title") == title) and (type_ is None or s["type"] == type_):
            return s
    raise AssertionError(f"section {title or type_} not found in {[s.get('title') or s['type'] for s in result['sections']]}")