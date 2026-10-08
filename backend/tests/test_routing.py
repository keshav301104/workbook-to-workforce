"""Workflow selection (offline lexical router; the LLM router is covered in test_llm_paths)."""
import pytest

from flowline.engine.router import lexical_route
from flowline.spec import loader

PARAPHRASES = {
    "Check today's inventory and identify products that need restocking.": "WF001",
    "What is running low in the warehouse?": "WF001",
    "Validate our product prices against the vendor list": "WF002",
    "Clean up this supplier file": "WF003",
    "Write a product description for the linen overshirt": "WF004",
    "Is ORD-1003 shipped yet?": "WF005",
    "Find duplicate SKUs": "WF006",
    "Plan a black friday promotion": "WF007",
    "Classify keywords by search intent": "WF008",
    "Who should handle the checkout bug fix?": "WF009",
    "Which workflows are slowest?": "WF010",
    "Who can build a FastAPI endpoint this week?": "WF009",
    "I need someone to build a FastAPI endpoint by Friday": "WF009",
    "How are our automations doing lately?": "WF010",
    "Check supplier prices": "WF002",
    "Do we have enough stock of wool beanies?": "WF001",
    "Plan a promo for the autumn knitwear launch": "WF007",
}


def test_every_excel_test_question_routes_correctly(settings):
    wfs = loader.get_registry().all()
    for wf in wfs:
        for t in wf.spec.test_requests:
            r = lexical_route(t.request, wfs)
            assert r.workflow_id == wf.id, (t.request, r)
            assert r.confidence >= settings.router_min_confidence


@pytest.mark.parametrize("request_text,expected", PARAPHRASES.items())
def test_paraphrases_route_correctly(settings, request_text, expected):
    r = lexical_route(request_text, loader.get_registry().all())
    assert r.workflow_id == expected


@pytest.mark.parametrize("text", ["What's the weather in Miami?", "tell me a joke", "hello"])
def test_out_of_scope_requests_match_nothing(settings, text):
    assert lexical_route(text, loader.get_registry().all()).workflow_id is None


def test_ambiguous_request_has_low_confidence(settings):
    r = lexical_route("show me the products", loader.get_registry().all())
    assert r.confidence < settings.router_min_confidence
    assert len(r.alternatives) >= 2


def test_reasoning_shows_original_words_not_stems(settings):
    r = lexical_route("Where is my order? I'm maya.patel@example.com", loader.get_registry().all())
    assert r.workflow_id == "WF005"
    assert "example" not in r.reasoning and "com" not in r.reasoning.split()