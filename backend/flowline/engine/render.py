"""Render a plan's result definition into JSON sections the UI (and CLI) can display.

Section types are generic (kpis, table, content, record, bars, alert, list, download),
so a new workflow gets a proper results view without any frontend work.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ..expr import ExpressionError, clean, evaluate, render, row_eval, to_text
from ..spec.models import ResultDef, SectionDef


def _columns(df: pd.DataFrame, spec: list) -> list[dict]:
    cols = []
    if not spec:
        spec = [c for c in df.columns if not str(c).startswith("_")]
    for c in spec:
        if isinstance(c, dict):
            cols.append({"key": c["key"], "label": c.get("label") or c["key"].replace("_", " ").capitalize(),
                         "format": c.get("format")})
        else:
            key, _, label = str(c).partition(":")
            cols.append({"key": key, "label": label or key.replace("_", " ").capitalize(), "format": None})
    return [c for c in cols if c["key"] in df.columns]


def _table(sec: SectionDef, names: dict) -> dict | None:
    data = render(sec.data, names)
    if data is None:
        return None
    df = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    cols = _columns(df, sec.columns)
    total = len(df)
    view = df.head(sec.limit or 200)
    tones = None
    if sec.highlight and not view.empty:
        tones = [None] * len(view)
        for tone, expr in sec.highlight.items():
            hits = row_eval(view, expr, names).fillna(False).astype(bool).tolist()
            tones = [t or (tone if h else None) for t, h in zip(tones, hits)]
    rows = [{c["key"]: clean(r.get(c["key"])) for c in cols} for r in view.to_dict("records")]
    return {"columns": cols, "rows": rows, "total": total, "tones": tones,
            "empty": render(sec.empty, names) if sec.empty else "No rows"}


def render_section(sec: SectionDef, names: dict) -> dict | None:
    if sec.when is not None and not evaluate(sec.when, names):
        return None
    out: dict[str, Any] = {"type": sec.type, "title": render(sec.title, names) if sec.title else None}
    if sec.type in ("summary", "alert"):
        out["text"] = to_text(render(sec.text, names))
        out["tone"] = sec.tone or "info"
    elif sec.type == "kpis":
        items = []
        for it in sec.items or []:
            items.append({"label": render(it.get("label"), names), "value": to_text(render(it.get("value"), names)),
                          "tone": render(it.get("tone"), names) if it.get("tone") else None,
                          "hint": render(it.get("hint"), names) if it.get("hint") else None})
        out["items"] = items
    elif sec.type == "table":
        t = _table(sec, names)
        if t is None:
            return None
        out.update(t)
    elif sec.type == "content":
        fields = []
        for f in sec.fields:
            v = render(f.get("value"), names)
            if isinstance(v, list):
                v = "\n".join(f"• {to_text(x)}" for x in v)
            fields.append({"label": render(f.get("label"), names), "value": to_text(v),
                           "meta": to_text(render(f.get("meta"), names)) if f.get("meta") else None,
                           "copy": f.get("copy", True)})
        out["fields"] = fields
    elif sec.type == "record":
        data = render(sec.data, names) if sec.data is not None else None
        items = []
        if sec.items:
            for it in sec.items:
                items.append({"label": render(it.get("label"), names), "value": to_text(render(it.get("value"), names)),
                              "tone": render(it.get("tone"), names) if it.get("tone") else None})
        elif isinstance(data, dict):
            items = [{"label": k.replace("_", " ").capitalize(), "value": to_text(v)} for k, v in data.items()]
        out["items"] = items
    elif sec.type == "list":
        items = render(sec.items, names)
        if isinstance(items, pd.DataFrame):
            items = [to_text(x) for x in items.iloc[:, 0].tolist()] if not items.empty else []
        out["items"] = [to_text(x) for x in (items or [])]
    elif sec.type == "bars":
        df = render(sec.data, names)
        if not isinstance(df, pd.DataFrame) or df.empty:
            return None
        out["items"] = [{"label": to_text(r[sec.label]), "value": float(clean(r[sec.value]) or 0)}
                        for r in df.head(sec.limit or 20).to_dict("records")]
        out["format"] = sec.format
        out["threshold"] = render(sec.threshold, names)
    elif sec.type == "download":
        files = []
        for f in sec.files:
            meta = render(f.get("file"), names)
            if meta and meta.get("url"):
                files.append({"label": render(f.get("label"), names), "url": meta["url"],
                              "filename": meta["filename"], "rows": meta.get("rows")})
        if not files:
            return None
        out["files"] = files
    return out


def render_result(result: ResultDef, names: dict) -> dict:
    sections = []
    for sec in result.sections:
        try:
            s = render_section(sec, names)
        except ExpressionError as e:
            # A section that references data from steps that did not run (e.g. after an
            # escalation) is simply not shown; anything else is surfaced.
            if "Unknown" in str(e):
                continue
            s = {"type": "alert", "tone": "danger", "text": f"Could not render section '{sec.title}': {e}"}
        if s:
            sections.append(s)
    def safe(t: str | None) -> str | None:
        if not t:
            return None
        try:
            return to_text(render(t, names))
        except ExpressionError:
            return None

    title = safe(result.title) or ""
    subtitle = safe(result.subtitle)
    return {"title": title, "subtitle": subtitle, "sections": sections}