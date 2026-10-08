"""Duplicate detection: exact key matches + attribute similarity with confidence."""
from __future__ import annotations

import re
from itertools import combinations
from typing import Any

import pandas as pd
from rapidfuzz import fuzz

from ..expr import is_missing
from .base import ToolContext, ToolResult, need_df, tool
from .data import _normalize_key


def _norm_name(s: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


class _UF:
    def __init__(self) -> None:
        self.p: dict = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


@tool("group_duplicates", "Group likely duplicate records: exact (normalised) key match = definite; high name + attribute similarity = possible, with a confidence score.", "similarity")
def group_duplicates(ctx: ToolContext, table: Any, key_column: str, name_column: str, attributes: list | None = None,
                     variant_attributes: list | None = None, block_by: str | None = None, high: float = 0.9,
                     medium: float = 0.8, label_columns: list | None = None) -> ToolResult:
    df = need_df(table, "table").reset_index(drop=True)
    attributes, variant_attributes = attributes or [], variant_attributes or []
    label_columns = label_columns or [key_column, name_column]
    df["_key"] = df[key_column].map(lambda v: _normalize_key(v, "sku"))
    df["_name"] = df[name_column].map(_norm_name)
    groups = []

    # 1) Definite duplicates: identical identifier after normalisation (case, spaces, punctuation)
    in_definite: set[int] = set()
    for key, g in df.groupby("_key"):
        if key is None or len(g) < 2:
            continue
        in_definite.update(g.index)
        groups.append({"match_type": "Exact SKU match", "confidence": "Definite", "score": 1.0, "rows": list(g.index),
                       "matching_fields": [key_column], "reason": f"Same {key_column.upper() if len(key_column) <= 3 else key_column} '{key}' after normalising case/spacing"})

    # 2) Possible duplicates: different identifiers, very similar name + same core attributes
    uf, best = _UF(), {}
    variants = 0
    blocks = df.groupby(block_by).groups.values() if block_by else [df.index]
    for idx in blocks:
        for i, j in combinations(list(idx), 2):
            a, b = df.loc[i], df.loc[j]
            if a["_key"] == b["_key"]:
                continue
            name_score = fuzz.WRatio(a["_name"], b["_name"]) / 100
            if name_score < 0.7:
                continue
            diff_variant = [v for v in variant_attributes if not is_missing(a[v]) and not is_missing(b[v])
                            and str(a[v]).strip().lower() != str(b[v]).strip().lower()]
            if diff_variant:
                variants += 1
                continue  # same product, different size/colour = a variant, not a duplicate
            comparable = [c for c in attributes if not is_missing(a[c]) and not is_missing(b[c])]
            same = [c for c in comparable if str(a[c]).strip().lower() == str(b[c]).strip().lower()]
            attr_score = len(same) / len(comparable) if comparable else 0.5
            score = round(0.6 * name_score + 0.4 * attr_score, 3)
            if score >= medium:
                uf.union(i, j)
                best[(i, j)] = (score, same, [c for c in comparable if c not in same])
    clusters: dict = {}
    for (i, j) in best:
        clusters.setdefault(uf.find(i), set()).update({i, j})
    for members in clusters.values():
        pairs = [v for (i, j), v in best.items() if i in members and j in members]
        score = max(p[0] for p in pairs)
        same = sorted(set.intersection(*[set(p[1]) for p in pairs])) if pairs else []
        differ = sorted(set().union(*[set(p[2]) for p in pairs])) if pairs else []
        groups.append({"match_type": "Attribute similarity", "confidence": "High" if score >= high else "Medium",
                       "score": score, "rows": sorted(members), "matching_fields": [name_column, *same],
                       "reason": f"Name similarity with matching {', '.join(same) or 'attributes'}"
                                 + (f"; differs on {', '.join(differ)}" if differ else "")})

    out = []
    for n, g in enumerate(sorted(groups, key=lambda g: (-g["score"], g["rows"][0])), start=1):
        sub = df.loc[g["rows"]]
        out.append({
            "group": f"G{n}",
            "confidence": g["confidence"],
            "score": round(g["score"] * 100),
            "match_type": g["match_type"],
            "records": len(sub),
            "skus": " | ".join(str(s).strip() for s in sub[key_column]),
            "names": " | ".join(str(s) for s in sub[name_column]),
            "sources": " | ".join(str(s) for s in sub["source"]) if "source" in sub else "",
            "matching_fields": ", ".join(g["matching_fields"]),
            "reason": g["reason"],
        })
    res = pd.DataFrame(out, columns=["group", "confidence", "score", "match_type", "records", "skus", "names", "sources",
                                     "matching_fields", "reason"])
    if variants:
        ctx.log(f"Ignored {variants} pair(s) that differ only by {'/'.join(variant_attributes)} (product variants)")
    d = int((res["confidence"] == "Definite").sum()) if len(res) else 0
    return ToolResult(res, f"{len(res)} duplicate group(s): {d} definite, {len(res) - d} possible")