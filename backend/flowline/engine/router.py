"""Workflow selection.

The routing catalogue is built from the Excel rows at request time, so a new row
is routable immediately. Primary path: the LLM picks a workflow with structured
output (id, confidence, reasoning, alternatives). Fallback path (no key / LLM
error): a BM25-style lexical scorer over the same Excel text. Both return the
same RouteResult so the rest of the engine doesn't care which one ran.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from ..llm import LLMUnavailable
from ..spec.models import Workflow

STOP = set("""a an the and or of to for in on at by with from this that these those is are was were be been it its
me my we our you your i please can could would should will show give get find tell let need needs which what
where how do does did today now all any some there their them then than into about as if not no yes
have has had got up out over more most just
""".split())
SYNONYMS = {
    "failing": "fail", "failure": "fail", "failures": "fail", "failed": "fail", "errors": "error",
    "restocking": "restock", "reorder": "restock", "replenish": "restock", "stock": "inventory",
    "duplicates": "duplicate", "dupes": "duplicate", "dedupe": "duplicate",
    "prices": "price", "pricing": "price", "cost": "price",
    "keywords": "keyword", "seo": "seo", "intent": "keyword",
    "spreadsheet": "file", "sheet": "file", "csv": "file", "xlsx": "file", "excel": "file", "upload": "file",
    "orders": "order", "shipment": "order", "tracking": "order", "delivery": "order", "package": "order",
    "assign": "assign", "assignment": "assign", "delegate": "assign", "developer": "employee", "employee": "employee",
    "staff": "employee", "engineer": "employee",
    "campaign": "campaign", "brief": "campaign", "promotion": "campaign", "launch": "campaign",
    "description": "content", "descriptions": "content", "copy": "content", "content": "content",
    "workflows": "workflow", "performance": "performance", "slow": "performance", "slowest": "performance",
    "shipped": "order", "ship": "order", "shipping": "order", "parcel": "order", "delivered": "order",
    "supplier": "vendor", "suppliers": "vendor", "cleaned": "clean", "cleanup": "clean",
    "handle": "assign", "owner": "assign", "allocate": "assign", "bug": "task", "ticket": "task", "fix": "task",
    "reliability": "performance", "success": "performance", "metrics": "performance",
    "automations": "workflow", "automation": "workflow", "agents": "workflow", "runs": "workflow",
    "someone": "employee", "somebody": "employee", "who": "employee", "build": "task", "implement": "task",
    "endpoint": "task", "feature": "task", "promo": "campaign", "marketing": "campaign",
    "costs": "price", "status": "order",
}


def tokens(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in STOP or len(w) < 2:
            continue
        w = SYNONYMS.get(w, w)
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        w = SYNONYMS.get(w, w)
        out.append(w)
    return out


@dataclass
class RouteResult:
    workflow_id: str | None
    confidence: float
    reasoning: str
    method: str                       # llm | lexical | manual | user
    alternatives: list[dict] = field(default_factory=list)
    note: str | None = None

    def as_dict(self, workflows: dict[str, Workflow]) -> dict:
        wf = workflows.get(self.workflow_id or "")
        return {"workflow_id": self.workflow_id, "workflow_name": wf.spec.name if wf else None,
                "confidence": round(self.confidence, 2), "reasoning": self.reasoning, "method": self.method,
                "alternatives": self.alternatives, "note": self.note}


FIELD_WEIGHTS = {"name": 3.0, "examples": 2.5, "trigger": 2.5, "inputs": 1.0, "output": 1.0, "steps": 0.6, "rules": 0.4}


def _fields(wf: Workflow) -> dict[str, str]:
    s = wf.spec
    examples = [t.request for t in s.test_requests] + (wf.plan.examples if wf.plan else [])
    return {"name": s.name, "trigger": s.trigger, "examples": " ".join(examples), "inputs": s.inputs_text,
            "output": s.expected_output, "steps": " ".join(s.steps), "rules": s.decision_logic}


def lexical_route(request: str, workflows: list[Workflow]) -> RouteResult:
    request = re.sub(r"\S+@\S+|https?://\S+", " ", request)   # identifiers carry no routing signal
    q = tokens(request)
    originals: dict[str, str] = {}
    for w in re.findall(r"[A-Za-z0-9]+", request):
        for t in tokens(w):
            originals.setdefault(t, w.lower())
    if not q or not workflows:
        return RouteResult(None, 0.0, "The request has no recognisable business terms.", "lexical")
    docs = {wf.id: {f: set(tokens(t)) for f, t in _fields(wf).items()} for wf in workflows}
    df = Counter()
    for d in docs.values():
        for t in set().union(*d.values()):
            df[t] += 1
    n = len(docs)
    idf = {t: math.log(1 + n / df[t]) for t in set(q) if df[t]}
    unknown_w = math.log(1 + n) * 0.5          # words no workflow mentions still count against coverage
    total = sum(idf.get(t, unknown_w) for t in q) or 1.0
    scores = {}
    for wid, d in docs.items():
        s = 0.0
        for t in q:
            w = max((FIELD_WEIGHTS[f] for f, toks in d.items() if t in toks), default=0.0)
            s += w * idf.get(t, 0.0)
        scores[wid] = s
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    (top, s1), s2 = ranked[0], (ranked[1][1] if len(ranked) > 1 else 0.0)
    max_possible = total * max(FIELD_WEIGHTS.values())
    coverage = sum(idf.get(t, 0) for t in q if any(t in toks for toks in docs[top].values())) / total
    if s1 <= 0 or coverage < 0.2:
        return RouteResult(None, round(min(coverage, 0.2), 2),
                           "None of the configured workflows matches this request.", "lexical",
                           [{"id": w, "score": round(s / s1, 2)} for w, s in ranked[:3] if s > 0] if s1 > 0 else [])
    margin = (s1 - s2) / s1
    strength = min(1.0, s1 / (0.45 * max_possible))
    # Ambiguity (small margin over the runner-up) is the strongest signal of an uncertain route.
    confidence = round(min(0.97, (0.45 * coverage + 0.25 * strength + 0.3) * (0.4 + 0.6 * min(1.0, margin * 1.6))), 2)
    matched = sorted({originals.get(t, t) for t in q if any(t in toks for toks in docs[top].values())})
    alts = [{"id": w, "score": round(s / s1, 2)} for w, s in ranked[1:4] if s > 0]
    return RouteResult(top, confidence, f"Matched on: {', '.join(matched)}.", "lexical", alts)


class _Decision(BaseModel):
    workflow_id: str = Field(description="ID of the single best workflow, or NONE if no workflow fits")
    confidence: float = Field(description="0-1. 0.9+ unambiguous, 0.6-0.9 likely, below 0.6 unsure")
    reasoning: str = Field(description="One sentence explaining the choice, referring to the request")
    alternatives: list[str] = Field(default_factory=list, description="Other plausible workflow IDs, best first")


def catalogue(workflows: list[Workflow]) -> str:
    lines = []
    for wf in workflows:
        s = wf.spec
        ex = "; ".join([t.request for t in s.test_requests] + (wf.plan.examples[:3] if wf.plan else []))
        lines.append(f"- {s.id} | {s.name}\n  Trigger: {s.trigger}\n  Inputs: {s.inputs_text}\n"
                     f"  Output: {s.expected_output}\n  Example requests: {ex}")
    return "\n".join(lines)


ROUTER_SYSTEM = """You are the router of a business workflow automation system.
Pick the ONE workflow that should handle the user's request, based on the catalogue below (it is generated from the
company's workflow spreadsheet). Judge by what the user wants done, not by shared words.
If the request is unrelated to every workflow, return workflow_id "NONE" with confidence 0.
If two workflows are equally plausible, return the better one with confidence below 0.6 and list the other.

Workflow catalogue:
{catalogue}"""


def route(request: str, workflows: list[Workflow], llm) -> RouteResult:
    lexical = lexical_route(request, workflows)
    if not llm.enabled:
        return lexical
    ids = {wf.id for wf in workflows}
    try:
        d = llm.structured(_Decision, ROUTER_SYSTEM.format(catalogue=catalogue(workflows)), f"Request: {request}")
        wid = d.workflow_id.strip().upper()
        if wid == "NONE":
            return RouteResult(None, 0.0, d.reasoning, "llm")
        if wid not in ids:
            raise LLMUnavailable(f"router returned unknown workflow '{d.workflow_id}'")
        alts = [{"id": a} for a in d.alternatives if a in ids and a != wid][:3]
        return RouteResult(wid, max(0.0, min(1.0, float(d.confidence))), d.reasoning, "llm", alts)
    except LLMUnavailable as e:
        lexical.note = f"LLM router unavailable ({e}); used lexical routing"
        return lexical