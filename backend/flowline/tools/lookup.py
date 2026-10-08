"""Lookup tools: identifier validation, record lookup (simulated API), fuzzy lookup, best-candidate selection."""
from __future__ import annotations

import re
from typing import Any

import pandas as pd
from rapidfuzz import fuzz, process
from rapidfuzz.utils import default_process

from ..expr import as_list, clean, is_missing, row_eval, wrap
from .base import ToolContext, ToolResult, need_df, tool


@tool("validate_identifier", "Check a value against identifier patterns (e.g. order id, email) and normalise it.", "lookup")
def validate_identifier(ctx: ToolContext, value: Any, patterns: dict, normalize: dict | None = None) -> ToolResult:
    """normalize: {kind: {"to": other_kind, "format": "ORD-{value}"}} turns e.g. '1004' into 'ORD-1004'."""
    raw = "" if is_missing(value) else str(value).strip()
    for kind, rx in patterns.items():
        m = re.fullmatch(rx, raw, re.I)
        if m:
            norm = raw.upper() if kind != "email" else raw.lower()
            rule = (normalize or {}).get(kind)
            if rule:
                norm = rule["format"].format(value=norm)
                ctx.log(f"Normalised '{raw}' to {norm}")
                kind = rule.get("to", kind)
            return ToolResult(wrap({"valid": True, "kind": kind, "value": norm}), f"'{raw}' is a valid {kind.replace('_', ' ')}")
    kinds = " or ".join(k.replace("_", " ") for k in patterns)
    return ToolResult(wrap({"valid": False, "kind": None, "value": raw}),
                      f"'{raw or '(empty)'}' is not a valid {kinds}")


@tool("lookup_records", "Find records whose field matches a value (or any of several values).", "lookup",
      simulated_api="Records API")
def lookup_records(ctx: ToolContext, table: Any, value: Any, field: str | None = None, kind: str | None = None,
                   fields: dict | None = None, api: str | None = None) -> ToolResult:
    df = need_df(table, "table")
    column = field or (fields or {}).get(kind or "", None)
    if column is None:
        column = next(iter((fields or {}).values()), None)
    if column is None or column not in df.columns:
        return ToolResult(wrap({"found": False, "count": 0, "records": df.head(0), "record": None}),
                          f"No searchable field for '{kind}'")
    values = {str(v).strip().lower() for v in as_list(value)}
    hits = df[df[column].map(lambda v: str(v).strip().lower() in values)].reset_index(drop=True)
    rec = None if hits.empty else wrap({k: clean(v) for k, v in hits.iloc[0].to_dict().items()})
    label = ", ".join(str(v).strip() for v in as_list(value)) or "(nothing)"
    return ToolResult(wrap({"found": not hits.empty, "count": len(hits), "records": hits, "record": rec}),
                      f"{len(hits)} record(s) where {column} = {label}")


@tool("fuzzy_lookup", "Find the closest record to free text across one or more columns.", "lookup")
def fuzzy_lookup(ctx: ToolContext, table: Any, query: Any, columns: list, min_score: int = 80) -> ToolResult:
    df = need_df(table, "table")
    q = "" if is_missing(query) else str(query).strip()
    if not q or df.empty:
        return ToolResult(wrap({"found": False, "record": None, "score": 0, "candidates": []}), "Nothing to look up")
    choices = {}
    for idx, r in df.iterrows():
        for c in columns:
            if not is_missing(r.get(c)):
                choices[(idx, c)] = str(r[c])
    best = process.extract(q, choices, scorer=fuzz.WRatio, processor=default_process, limit=5)
    seen, candidates = set(), []
    for _text, score, (idx, col) in best:
        if idx in seen:
            continue
        seen.add(idx)
        candidates.append({"index": idx, "label": str(df.loc[idx, columns[0]]), "score": round(score)})
    top = candidates[0] if candidates else None
    if top and top["score"] >= min_score:
        rec = wrap({k: clean(v) for k, v in df.loc[top["index"]].to_dict().items()})
        return ToolResult(wrap({"found": True, "record": rec, "score": top["score"], "candidates": candidates}),
                          f"Matched '{q}' to {top['label']} ({top['score']}% similarity)")
    return ToolResult(wrap({"found": False, "record": None, "score": top["score"] if top else 0,
                            "candidates": candidates}),
                      f"No confident match for '{q}' (best {top['score'] if top else 0}%)")


@tool("select_best", "Pick the top row that satisfies an eligibility rule; return it with the runners-up.", "decision")
def select_best(ctx: ToolContext, table: Any, where: str | None = None, alternatives: int = 3) -> ToolResult:
    df = need_df(table, "table")
    eligible = df
    if where and not df.empty:
        eligible = df[row_eval(df, where, ctx.names).fillna(False).astype(bool).values]
    if eligible.empty:
        return ToolResult(wrap({"found": False, "record": None, "alternatives": eligible, "eligible": 0}),
                          "No row satisfies the eligibility rule")
    rec = wrap({k: clean(v) for k, v in eligible.iloc[0].to_dict().items()})
    alts = eligible.iloc[1:1 + alternatives].reset_index(drop=True)
    return ToolResult(wrap({"found": True, "record": rec, "alternatives": alts, "eligible": len(eligible)}),
                      f"Selected 1 of {len(eligible)} eligible row(s)")


@tool("match_rows", "Select rows matching a free-text reference (e.g. 'new collection', a category or names).", "lookup")
def match_rows(ctx: ToolContext, table: Any, query: Any, columns: list, newest_by: str | None = None,
               group_column: str | None = None, min_score: int = 75) -> ToolResult:
    df = need_df(table, "table")
    q = "" if is_missing(query) else str(query).lower()
    if not q:
        return ToolResult(df.head(0), "No product reference given")
    if newest_by and group_column and re.search(r"\b(new|newest|latest|upcoming)\b", q):
        latest = df.sort_values(newest_by).iloc[-1][group_column]
        out = df[df[group_column] == latest].reset_index(drop=True)
        ctx.log(f"'new collection' resolved to the most recent {group_column}: {latest}")
        return ToolResult(out, f"{len(out)} products in {latest}")
    mask = pd.Series(False, index=df.index)
    for c in columns:
        mask |= df[c].map(lambda v: not is_missing(v) and fuzz.partial_ratio(q, str(v).lower()) >= min_score)
    out = df[mask].reset_index(drop=True)
    return ToolResult(out, f"{len(out)} rows match '{query}'")