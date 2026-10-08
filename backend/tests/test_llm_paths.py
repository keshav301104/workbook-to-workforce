"""Exercise the LLM code paths (schema building, parsing, label validation, fallbacks)
with a fake model, so they are tested without network access or an API key."""
from typing import get_args

import pytest
from pydantic import BaseModel

from flowline.engine.router import lexical_route
from flowline.llm import LLMUnavailable, set_llm
from flowline.spec import loader

from .conftest import events_of, result_of, section


class FakeLLM:
    """Returns schema-valid answers; records every call."""

    enabled = True
    label = "fake · test-model"

    def __init__(self, broken=False):
        self.calls = []
        self.broken = broken

    def structured(self, schema: type[BaseModel], system: str, user: str):
        self.calls.append(schema.__name__)
        if self.broken:
            raise LLMUnavailable("simulated provider outage")
        name = schema.__name__
        if name == "_Decision":
            req = user.removeprefix("Request: ")
            r = lexical_route(req, loader.get_registry().all())
            return schema(workflow_id=r.workflow_id or "NONE", confidence=0.93, reasoning="fake", alternatives=[])
        if name == "WorkflowInputs":
            return schema()                                   # nothing stated -> patterns fill in
        if name == "Batch":                                    # classify: label every item 'commercial'
            n = user.count("\n") + 1 if "Items:" in user else 0
            item_t = schema.model_fields["items"].annotation.__args__[0]
            label = "commercial" if "commercial" in get_args(item_t.model_fields["label"].annotation) else get_args(item_t.model_fields["label"].annotation)[0]
            return schema(items=[item_t(index=i, label=label) for i in range(n - 1)])
        if name == "MapBatch":
            item_t = schema.model_fields["items"].annotation.__args__[0]
            target = get_args(item_t.model_fields["target"].annotation)[0]
            n = user.count("\n")
            return schema(items=[item_t(index=i, target=target) for i in range(n)])
        if name == "Extracted":
            return schema(required_skills=["React", "STRIPE", "cobol"], unlisted_skills=[])
        values = {}
        for f, info in schema.model_fields.items():
            values[f] = ["LLM item one", "LLM item two", "LLM item three"] if "list" in str(info.annotation) else f"LLM {f}"
        return schema(**values)

    def text(self, system, user):
        raise LLMUnavailable("text not faked")


@pytest.fixture()
def fake(settings):
    f = FakeLLM()
    set_llm(f)
    yield f
    set_llm(None)


def test_llm_router_and_generation_paths(engine, fake):
    ev, _ = engine.run_to_end("Generate SEO content for the Quilted Liner Vest")
    route = events_of(ev, "route")[0]
    assert route["method"] == "llm" and route["workflow_id"] == "WF004"
    r = result_of(ev)
    content = {f["label"]: f["value"] for f in section(r, type_="content")["fields"]}
    assert content["SEO title"] == "LLM seo_title"
    engines = {e["step_id"]: e.get("engine") for e in events_of(ev, "step_finished")}
    assert engines["description"] == "llm"
    assert "Generated" in fake.calls and "WorkflowInputs" in fake.calls


def test_llm_classifier_output_is_constrained_to_labels(engine, fake):
    ev, _ = engine.run_to_end("keywords: linen shirt, how to wash linen")
    report = section(result_of(ev), "Keyword report")["rows"]
    assert {x["intent"] for x in report} <= {"informational", "commercial", "transactional", "navigational"}


def test_llm_extracted_skills_are_filtered_to_known_vocabulary(engine, fake):
    ev, _ = engine.run_to_end("Assign a developer. task: fix the checkout")
    finished = {e["step_id"]: e for e in events_of(ev, "step_finished")}
    assert "required_skills=['react', 'stripe']" in finished["requirements"]["summary"]   # 'cobol' dropped


def test_provider_outage_falls_back_without_failing(engine, settings):
    set_llm(FakeLLM(broken=True))
    try:
        ev, _ = engine.run_to_end("Generate SEO content for the Quilted Liner Vest")
        route = events_of(ev, "route")[0]
        assert route["method"] == "lexical" and "unavailable" in route["note"]
        assert result_of(ev)["status"] == "completed"
        logs = [e["message"] for e in events_of(ev, "step_log")]
        assert any("deterministic fallback" in m for m in logs)
    finally:
        set_llm(None)