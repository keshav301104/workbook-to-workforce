"""LLM-backed tools. Each has a deterministic fallback so the system never hard-fails
when the model is unavailable, and every output is validated against a schema."""
from __future__ import annotations

import json
import re
from datetime import timedelta
from typing import Any, Literal, Optional

import pandas as pd
from pydantic import BaseModel, Field, create_model
from rapidfuzz import fuzz

from ..expr import _keyword_label, _to_date, as_list, clean, is_missing, render, wrap
from ..llm import LLMUnavailable
from .base import ToolContext, ToolError, ToolResult, need_df, tool

GROUNDING = (
    "You are a precise assistant running one step of an automated business workflow. "
    "Use ONLY the facts provided. Never invent product attributes, numbers, prices, dates, people or claims "
    "that are not in the facts. Keep wording concrete and professional."
)


def _jsonable(v: Any) -> Any:
    if isinstance(v, pd.DataFrame):
        return [{k: clean(x) for k, x in r.items()} for r in v.head(40).to_dict("records")]
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return clean(v)


def _fallback_note(ctx: ToolContext, err: Exception | None) -> None:
    if err is None:
        ctx.log("Offline mode: using the deterministic template for this step", "info")
    else:
        ctx.log(f"LLM unavailable ({err}); used the deterministic fallback", "warn")


def _field_model(name: str, fields: dict) -> type[BaseModel]:
    defs = {}
    for fname, spec in fields.items():
        spec = spec if isinstance(spec, dict) else {"description": str(spec)}
        desc = spec.get("description", "")
        if spec.get("max_length"):
            desc += f" (at most {spec['max_length']} characters)"
        if spec.get("type") == "list":
            defs[fname] = (list[str], Field(description=desc))
        else:
            defs[fname] = (str, Field(description=desc))
    return create_model(name, **defs)


@tool("llm_generate", "Generate structured text fields grounded in given facts (LLM, template fallback).", "language", llm=True)
def llm_generate(ctx: ToolContext, task: str, facts: Any, fields: dict, rules: list | None = None,
                 avoid: list | None = None, fallback: dict | None = None) -> ToolResult:
    facts_j = _jsonable(facts)
    avoid = [a for a in as_list(avoid)]
    err: Exception | None = None
    if ctx.llm.enabled:
        try:
            schema = _field_model("Generated", fields)
            sys = GROUNDING
            if rules:
                sys += "\nRules:\n" + "\n".join(f"- {r}" for r in rules)
            if avoid:
                sys += ("\nThese attributes are MISSING. Do not mention, guess or imply any value for them: "
                        + ", ".join(avoid))
            user = f"Task: {task}\n\nFacts (JSON):\n{json.dumps(facts_j, indent=1, default=str)}"
            out = ctx.llm.structured(schema, sys, user).model_dump()
            ctx.log(f"Generated {', '.join(fields)} with {ctx.llm.label}")
            return ToolResult(wrap(out), f"Generated {len(out)} field(s) with the LLM", engine="llm")
        except LLMUnavailable as e:
            err = e
    if not fallback:
        raise ToolError("LLM unavailable and this step has no fallback template")
    _fallback_note(ctx, err)
    names = {**ctx.names, "facts": wrap(facts) if isinstance(facts, dict) else facts}
    out = {k: render(v, names) for k, v in fallback.items() if k in fields}
    return ToolResult(wrap(out), f"Generated {len(out)} field(s) from templates", engine="rules")


@tool("llm_extract", "Extract structured fields from free text; list fields are constrained to a vocabulary.", "language", llm=True)
def llm_extract(ctx: ToolContext, text: Any, fields: dict, aliases: dict | None = None,
                fallback: dict | None = None) -> ToolResult:
    text_s = "" if is_missing(text) else str(text)
    aliases = aliases or {}
    err: Exception | None = None
    if ctx.llm.enabled:
        try:
            defs = {}
            for f, spec in fields.items():
                desc = spec.get("description", "")
                if spec.get("vocabulary"):
                    desc += f". Choose only from: {', '.join(map(str, spec['vocabulary']))}"
                typ = list[str] if spec.get("type") == "list" else (Optional[float] if spec.get("type") == "number" else Optional[str])
                defs[f] = (typ, Field(default=None, description=desc))
            schema = create_model("Extracted", **defs)
            out = ctx.llm.structured(schema, GROUNDING + " Extract only what the text states or clearly implies.",
                                     f"Text: {text_s}").model_dump()
            for f, spec in fields.items():
                if spec.get("vocabulary") and isinstance(out.get(f), list):
                    vocab = {str(v).lower(): v for v in spec["vocabulary"]}
                    out[f] = [vocab[str(x).lower()] for x in out[f] if str(x).lower() in vocab]
            return ToolResult(wrap(out), "Extracted: " + "; ".join(f"{k}={v}" for k, v in out.items()), engine="llm")
        except LLMUnavailable as e:
            err = e
    _fallback_note(ctx, err)
    low = f" {text_s.lower()} "
    out: dict[str, Any] = {}
    for f, spec in fields.items():
        vocab = spec.get("vocabulary")
        if vocab:
            found = []
            for term in vocab:
                t = str(term).lower()
                keys = [t, *[a.lower() for a, canon in aliases.items() if str(canon).lower() == t]]
                if any(re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", low) for k in keys):
                    found.append(term)
            out[f] = found
        else:
            out[f] = None
    for k, tpl in (fallback or {}).items():
        out[k] = render(tpl, {**ctx.names, "extracted": wrap(out), "text": text_s})
    return ToolResult(wrap(out), "Extracted: " + "; ".join(f"{k}={v}" for k, v in out.items()), engine="rules")


@tool("llm_classify", "Classify each row into exactly one of a fixed set of labels (LLM batch, keyword-rule fallback).", "language", llm=True)
def llm_classify(ctx: ToolContext, table: Any, column: str, labels: dict, into: str, rules: dict | None = None,
                 default: str | None = None, context: str | None = None, batch_size: int = 40) -> ToolResult:
    df = need_df(table, "table").copy()
    items = [str(x) for x in df[column].tolist()]
    allowed = list(labels)
    result: list[str | None] = [None] * len(items)
    source = ["rules"] * len(items)
    err: Exception | None = None
    if ctx.llm.enabled and items:
        Label = Literal[tuple(allowed)]  # type: ignore[valid-type]
        Item = create_model("Item", index=(int, ...), label=(Label, ...))
        Batch = create_model("Batch", items=(list[Item], ...))
        try:
            for start in range(0, len(items), batch_size):
                chunk = items[start:start + batch_size]
                listing = "\n".join(f"{start + i}: {t}" for i, t in enumerate(chunk))
                sys = (GROUNDING + "\nClassify every item into exactly one label:\n"
                       + "\n".join(f"- {k}: {v}" for k, v in labels.items())
                       + (f"\nContext: {context}" if context else ""))
                out = ctx.llm.structured(Batch, sys, f"Items:\n{listing}")
                for it in out.items:
                    if 0 <= it.index < len(items) and it.label in allowed:
                        result[it.index], source[it.index] = it.label, "llm"
            ctx.log(f"Classified {sum(s == 'llm' for s in source)} item(s) with {ctx.llm.label}")
        except LLMUnavailable as e:
            err = e
    if any(r is None for r in result):
        if err or not ctx.llm.enabled:
            _fallback_note(ctx, err)
        for i, t in enumerate(items):
            if result[i] is None:
                result[i] = _keyword_label(t, rules or {}, default or allowed[0])
    df[into] = result
    df[f"{into}_source"] = source
    counts = df[into].value_counts().to_dict()
    engine = "llm" if all(s == "llm" for s in source) else ("rules" if all(s == "rules" for s in source) else "mixed")
    return ToolResult(df, "Labels: " + ", ".join(f"{k} {v}" for k, v in counts.items()), engine=engine)


@tool("llm_map", "Map each row to the best target from a reference table (LLM, term/fuzzy fallback).", "language", llm=True)
def llm_map(ctx: ToolContext, table: Any, column: str, targets: Any, target_key: str, into: str,
            target_terms: str | None = None, bring: list | None = None, default: str | None = None) -> ToolResult:
    df = need_df(table, "table").copy()
    tdf = need_df(targets, "targets")
    keys = [str(k) for k in tdf[target_key]]
    terms = {str(r[target_key]): as_list(r[target_terms]) if target_terms else [] for _, r in tdf.iterrows()}
    items = [str(x) for x in df[column]]
    mapped: list[str | None] = [None] * len(items)
    err: Exception | None = None
    if ctx.llm.enabled and items:
        Target = Literal[tuple(keys)]  # type: ignore[valid-type]
        Item = create_model("MapItem", index=(int, ...), target=(Target, ...))
        Batch = create_model("MapBatch", items=(list[Item], ...))
        try:
            ref = "\n".join(f"- {k}: {', '.join(terms[k])}" for k in keys)
            listing = "\n".join(f"{i}: {t}" for i, t in enumerate(items))
            out = ctx.llm.structured(Batch, GROUNDING + f"\nMap every item to the best target. Targets:\n{ref}",
                                     f"Items:\n{listing}")
            for it in out.items:
                if 0 <= it.index < len(items):
                    mapped[it.index] = it.target
        except LLMUnavailable as e:
            err = e
    if any(m is None for m in mapped):
        if err or not ctx.llm.enabled:
            _fallback_note(ctx, err)
        for i, t in enumerate(items):
            if mapped[i] is not None:
                continue
            low = f" {t.lower()} "
            scores = {}
            for k in keys:
                s = sum(len(term) for term in terms[k]
                        if re.search(rf"(?<![a-z0-9]){re.escape(term.lower())}(?:s|es)?(?![a-z0-9])", low))
                scores[k] = s + fuzz.partial_ratio(t.lower(), k.lower()) / 1000
            best = max(scores, key=scores.get)
            mapped[i] = best if scores[best] >= 1 else (default or best)
    df[into] = mapped
    for b in bring or []:
        lookup = dict(zip(tdf[target_key].astype(str), tdf[b]))
        df[b] = df[into].map(lookup)
    counts = df[into].value_counts().to_dict()
    return ToolResult(df, f"Mapped {len(df)} rows to {len(counts)} target(s)", engine="llm" if not err and ctx.llm.enabled else "rules")


@tool("validate_text", "Check generated text: length limits and that missing attributes were not invented.", "language")
def validate_text(ctx: ToolContext, texts: dict, max_length: dict | None = None, missing: list | None = None,
                  vocabulary: Any = None) -> ToolResult:
    max_length = max_length or {}
    rows = []
    vocab_df = vocabulary if isinstance(vocabulary, pd.DataFrame) else None
    for field, text in texts.items():
        t = "" if is_missing(text) else str(text)
        limit = max_length.get(field)
        if limit:
            ok = len(t) <= int(limit)
            rows.append({"field": field, "check": f"Length ≤ {limit}", "result": "Pass" if ok else "Fail",
                         "detail": f"{len(t)} characters"})
        if not t.strip():
            rows.append({"field": field, "check": "Not empty", "result": "Fail", "detail": "empty text"})
        for attr in as_list(missing):
            if vocab_df is None or attr not in vocab_df.columns:
                continue
            values = [str(v) for v in vocab_df[attr].dropna().unique()]
            hits = [v for v in values if re.search(rf"(?<![a-z]){re.escape(v.lower())}(?![a-z])", t.lower())]
            rows.append({"field": field, "check": f"No invented {attr.replace('_', ' ')}",
                         "result": "Fail" if hits else "Pass",
                         "detail": f"mentions {', '.join(hits)}" if hits else "none mentioned"})
    df = pd.DataFrame(rows, columns=["field", "check", "result", "detail"])
    failed = int((df["result"] == "Fail").sum())
    for _, r in df[df["result"] == "Fail"].iterrows():
        ctx.log(f"{r['field']}: {r['check']} failed ({r['detail']})", "warn")
    return ToolResult(wrap({"checks": df, "passed": failed == 0, "failed": failed}),
                      "All text checks passed" if failed == 0 else f"{failed} text check(s) failed")


@tool("build_timeline", "Split a date range into phases by share of the duration.", "planning")
def build_timeline(ctx: ToolContext, start: Any, end: Any, phases: list) -> ToolResult:
    s, e = _to_date(start), _to_date(end)
    if s is None or e is None:
        raise ToolError("Timeline needs a valid start and end date")
    if e < s:
        raise ToolError("End date is before start date")
    total = (e - s).days + 1
    rows, cursor = [], s
    weights = [float(p.get("share", 1)) for p in phases]
    for i, p in enumerate(phases):
        days = max(1, round(total * weights[i] / sum(weights))) if i < len(phases) - 1 else (e - cursor).days + 1
        p_end = min(e, cursor + timedelta(days=days - 1))
        rows.append({"phase": p["name"], "start": cursor.isoformat(), "end": p_end.isoformat(),
                     "days": (p_end - cursor).days + 1, "focus": p.get("focus", "")})
        cursor = min(e, p_end + timedelta(days=1))
    return ToolResult(pd.DataFrame(rows), f"{len(rows)} phases over {total} days")