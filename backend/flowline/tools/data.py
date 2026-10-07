"""Generic table tools: read, normalise, validate, filter, compute, join, aggregate, export."""
from __future__ import annotations

import re
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from ..expr import clean, is_missing, row_eval, to_text, wrap
from ..llm import LLMUnavailable
from .base import ToolContext, ToolError, ToolResult, need_df, tool

READERS = {".csv": "csv", ".tsv": "tsv", ".txt": "csv", ".xlsx": "excel", ".xls": "excel", ".xlsm": "excel",
           ".json": "json"}


def _read(ctx: ToolContext, path: str, sheet: Any, raw: bool = False) -> pd.DataFrame:
    p = ctx.resolve_path(path)
    kind = READERS.get(p.suffix.lower())
    if kind is None:
        raise ToolError(f"Unsupported file type '{p.suffix}'. Use CSV, TSV, XLSX or JSON.")
    if kind == "excel":
        xl = pd.ExcelFile(p)
        name = sheet if sheet is not None else xl.sheet_names[0]
        if len(xl.sheet_names) > 1:
            ctx.log(f"Workbook has sheets {xl.sheet_names}; reading '{name}'")
        if raw:  # keep 'N/A', 'null'... as text so cleaning can report them instead of silently dropping
            return pd.read_excel(xl, sheet_name=name, dtype=object, keep_default_na=False, na_values=[""])
        return pd.read_excel(xl, sheet_name=name, dtype=object)
    if kind == "json":
        return pd.read_json(p)
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(p, sep="\t" if kind == "tsv" else ",", encoding=enc, dtype=object,
                               keep_default_na=not raw, na_values=[""] if raw else None)
        except UnicodeDecodeError:
            ctx.log(f"Encoding {enc} failed, trying next", "warn")
    raise ToolError(f"Could not decode {p.name}")


def _coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Convert columns that are fully numeric to numbers (CSV is read as text)."""
    for c in df.columns:
        if df[c].dtype == object:
            conv = pd.to_numeric(df[c], errors="coerce")
            if conv.notna().sum() == df[c].notna().sum() and df[c].notna().any():
                df[c] = conv
    return df


@tool("load_table", "Read a CSV/XLSX/JSON file (or an inline list of values) into a table.", "data")
def load_table(ctx: ToolContext, path: Any = None, sheet: Any = None, inline: Any = None, column: str = "value",
               optional: bool = False, raw: bool = False, ensure: list | None = None) -> ToolResult:
    res = _load_table(ctx, path, sheet, inline, column, optional, raw)
    for c in ensure or []:
        if c not in res.value.columns:
            res.value[c] = None
    return res


def _load_table(ctx: ToolContext, path: Any, sheet: Any, inline: Any, column: str, optional: bool,
                raw: bool) -> ToolResult:
    if not is_missing(path) and optional:
        try:
            ctx.resolve_path(str(path))
        except ToolError:
            return ToolResult(pd.DataFrame(), f"{path} does not exist yet; continuing without it")
    if not is_missing(path):
        df = _read(ctx, str(path), sheet, raw)
        src = str(path).split("/")[-1].split("__", 1)[-1]
        if not raw:
            df = _coerce_numeric(df)
    elif not is_missing(inline):
        items = inline if isinstance(inline, list) else [x for x in re.split(r"[\n;,]", str(inline))]
        items = [str(x).strip() for x in items if str(x).strip()]
        df = pd.DataFrame({column: items})
        src = "the request text"
    elif optional:
        return ToolResult(pd.DataFrame(), "No source provided; continuing with an empty table")
    else:
        raise ToolError("No file or values were provided to load")
    return ToolResult(df, f"Loaded {len(df)} rows × {len(df.columns)} columns from {src}")


@tool("concat_tables", "Stack several tables with the same columns.", "data")
def concat_tables(ctx: ToolContext, tables: list) -> ToolResult:
    frames = [t for t in tables if isinstance(t, pd.DataFrame) and not t.empty]
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return ToolResult(df, f"Combined {len(frames)} sources into {len(df)} rows")


def _norm_header(h: Any) -> str:
    h = str(h).lower().replace("($)", "").replace("#", " number ")
    return re.sub(r"[^a-z0-9]+", " ", h).strip()


class _ColumnMap(BaseModel):
    mapping: dict[str, str] = Field(description="canonical field -> exact source column name; omit if no column fits")


@tool("detect_columns", "Match messy source headers to a canonical schema (exact alias, then fuzzy, then LLM).", "data", llm=True)
def detect_columns(ctx: ToolContext, table: Any, schema: dict, required: list | None = None) -> ToolResult:
    df = need_df(table, "table")
    required = required or []
    sources = list(df.columns)
    scores: list[tuple[float, str, str]] = []
    for canon, aliases in schema.items():
        names = [canon, *aliases]
        for s in sources:
            ns = _norm_header(s)
            best = max((100.0 if ns == _norm_header(a) else fuzz.token_set_ratio(ns, _norm_header(a))) for a in names)
            scores.append((best, canon, s))
    mapping, conf, used = {}, {}, set()
    for score, canon, s in sorted(scores, reverse=True):
        if score < 80 or canon in mapping or s in used:
            continue
        mapping[canon], conf[canon] = s, round(score / 100, 2)
        used.add(s)
    engine = "rules"
    unresolved = [r for r in required if r not in mapping]
    if unresolved and ctx.llm.enabled:
        try:
            free = [s for s in sources if s not in used]
            out = ctx.llm.structured(_ColumnMap, "You map spreadsheet columns to a schema. Only use listed columns.",
                                     f"Schema fields needing a column: {unresolved}\nAvailable columns: {free}")
            for k, v in out.mapping.items():
                if k in unresolved and v in free:
                    mapping[k], conf[k] = v, 0.75
                    used.add(v)
            engine = "llm"
        except LLMUnavailable as e:
            ctx.log(f"LLM column matching unavailable: {e}", "warn")
    for canon, s in mapping.items():
        ctx.log(f"'{str(s).strip()}' → {canon} ({int(conf[canon] * 100)}% match)")
    missing_required = [r for r in required if r not in mapping]
    unmapped = [s for s in sources if s not in used]
    value = wrap({"mapping": mapping, "confidence": conf, "unmapped": unmapped, "missing_required": missing_required})
    msg = f"Detected {len(mapping)} of {len(schema)} schema fields"
    if unmapped:
        msg += f"; {len(unmapped)} extra column(s) kept as-is"
    return ToolResult(value, msg, engine=engine)


def _snake(s: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).strip().lower()).strip("_")


@tool("rename_columns", "Rename columns using a mapping (canonical -> source); other columns become snake_case.", "data")
def rename_columns(ctx: ToolContext, table: Any, mapping: dict, keep_unmapped: bool = True) -> ToolResult:
    df = need_df(table, "table").copy()
    inverse = {src: canon for canon, src in mapping.items()}
    new_cols = {c: inverse.get(c, _snake(c)) for c in df.columns}
    df = df.rename(columns=new_cols)
    if not keep_unmapped:
        df = df[[c for c in df.columns if c in mapping]]
    return ToolResult(df, f"Normalized column names: {', '.join(map(str, df.columns))}")


@tool("clean_values", "Trim text, standardise case, parse numbers and report value problems as warnings.", "data")
def clean_values(ctx: ToolContext, table: Any, uppercase: list | None = None, numeric: list | None = None,
                 drop_empty_rows: bool = True, warn_duplicates: list | None = None) -> ToolResult:
    df = need_df(table, "table").copy()
    if "source_row" not in df.columns:
        df.insert(0, "source_row", df.index + 2)   # spreadsheet row number (header = row 1)
    warnings = []
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(lambda v: (str(v).strip() or None) if not is_missing(v) else None)
    dropped = 0
    if drop_empty_rows:
        data_cols = [c for c in df.columns if c != "source_row"]
        mask = df[data_cols].isna().all(axis=1)
        dropped = int(mask.sum())
        df = df[~mask]
    for c in uppercase or []:
        if c in df.columns:
            df[c] = df[c].map(lambda v: None if is_missing(v) else str(v).upper())
    for c in numeric or []:
        if c not in df.columns:
            continue

        def parse(v: Any, row: Any, col: str = c) -> Any:
            if is_missing(v):
                return None
            s = re.sub(r"[,$€£\s]", "", str(v))
            try:
                return float(s)
            except ValueError:
                warnings.append({"source_row": row, "field": col, "value": v, "issue": f"'{v}' is not a number"})
                return None

        df[c] = [parse(v, r) for v, r in zip(df[c], df["source_row"])]
    for c in warn_duplicates or []:
        if c in df.columns:
            dup = df[df[c].notna() & df.duplicated(c, keep="first")]
            for _, r in dup.iterrows():
                warnings.append({"source_row": r["source_row"], "field": c, "value": r[c],
                                 "issue": f"duplicate {c} (first seen earlier in the file)"})
    wdf = pd.DataFrame(warnings, columns=["source_row", "field", "value", "issue"])
    msg = f"Cleaned {len(df)} rows"
    if dropped:
        msg += f", dropped {dropped} empty row(s)"
    if len(wdf):
        msg += f", {len(wdf)} value warning(s)"
    return ToolResult(wrap({"table": df.reset_index(drop=True), "warnings": wdf, "dropped_empty": dropped}), msg)


@tool("validate_required", "Split rows into valid / invalid based on required fields.", "data")
def validate_required(ctx: ToolContext, table: Any, fields: list) -> ToolResult:
    df = need_df(table, "table").copy()
    for f in fields:
        if f not in df.columns:
            df[f] = None
    issues = []
    for _, r in df.iterrows():
        miss = [f for f in fields if is_missing(r[f])]
        issues.append("Missing " + " and ".join(m.upper() if len(m) <= 3 else m.replace("_", " ") for m in miss)
                      if miss else None)
    df["issue"] = issues
    invalid = df[df["issue"].notna()].reset_index(drop=True)
    valid = df[df["issue"].isna()].drop(columns=["issue"]).reset_index(drop=True)
    return ToolResult(wrap({"valid": valid, "invalid": invalid}),
                      f"{len(valid)} valid, {len(invalid)} invalid (required: {', '.join(fields)})")


@tool("filter_rows", "Keep rows where an expression is true.", "data")
def filter_rows(ctx: ToolContext, table: Any, where: str) -> ToolResult:
    df = need_df(table, "table")
    if df.empty:
        return ToolResult(df, "Nothing to filter (empty table)")
    mask = row_eval(df, where, ctx.names).fillna(False).astype(bool)
    out = df[mask.values].reset_index(drop=True)
    return ToolResult(out, f"{len(out)} of {len(df)} rows match `{where}`")


@tool("compute_column", "Add or overwrite columns from per-row expressions.", "data")
def compute_column(ctx: ToolContext, table: Any, columns: dict) -> ToolResult:
    df = need_df(table, "table").copy()
    if df.empty:
        for c in columns:
            df[c] = []
        return ToolResult(df, "Empty table; no values computed")
    for col, expr in columns.items():
        values = row_eval(df, str(expr), ctx.names)
        if values.map(lambda v: (isinstance(v, (int, float)) and not isinstance(v, bool)) or v is None).all():
            values = pd.to_numeric(values, errors="coerce")
        df[col] = values.values
    return ToolResult(df, f"Computed {', '.join(columns)} for {len(df)} rows")


@tool("flag_rows", "Apply a decision rule to every row and mark the rows where it holds.", "decision",
      raw_args=("reason",))
def flag_rows(ctx: ToolContext, table: Any, when: str, flag: str = "flagged", reason: str | None = None) -> ToolResult:
    df = need_df(table, "table").copy()
    if df.empty:
        df[flag] = []
        return ToolResult(df, "Empty table; nothing to flag")
    df[flag] = row_eval(df, when, ctx.names).fillna(False).astype(bool).values
    if reason:
        from ..expr import TEMPLATE_RE, evaluate

        texts = []
        for rec, hit in zip(df.to_dict("records"), df[flag]):
            if not hit:
                texts.append(None)
                continue
            names = {**ctx.names, **{k: clean(v) for k, v in rec.items()}}
            texts.append(TEMPLATE_RE.sub(lambda m: to_text(evaluate(m.group(1), names)), reason))
        df[f"{flag}_reason"] = texts
    n = int(df[flag].sum())
    ctx.log(f"Rule `{when}` is true for {n} row(s)")
    return ToolResult(df, f"Flagged {n} of {len(df)} rows")


def _normalize_key(v: Any, mode: str | None) -> Any:
    if is_missing(v):
        return None
    s = str(v)
    if mode == "sku":
        return re.sub(r"[^A-Z0-9]", "", s.upper())
    if mode == "text":
        return re.sub(r"\s+", " ", s.strip().lower())
    return s


@tool("join_tables", "Match two tables on a key (optionally normalised); returns matched and unmatched rows.", "data")
def join_tables(ctx: ToolContext, left: Any, right: Any, left_on: str, right_on: str | None = None,
                how: str = "inner", normalize: str | None = None) -> ToolResult:
    ldf, rdf = need_df(left, "left").copy(), need_df(right, "right").copy()
    right_on = right_on or left_on
    ldf["_key"] = ldf[left_on].map(lambda v: _normalize_key(v, normalize))
    rdf["_key"] = rdf[right_on].map(lambda v: _normalize_key(v, normalize)) if not rdf.empty else []
    merged = ldf.merge(rdf, on="_key", how="outer", indicator=True, suffixes=("", "_right"))
    matched = merged[merged["_merge"] == "both"].drop(columns=["_merge", "_key"]).reset_index(drop=True)
    left_only = ldf[~ldf["_key"].isin(rdf["_key"])].drop(columns=["_key"]).reset_index(drop=True)
    right_only = rdf[~rdf["_key"].isin(ldf["_key"])].drop(columns=["_key"]).reset_index(drop=True)
    joined = matched if how == "inner" else ldf.merge(rdf, on="_key", how="left", suffixes=("", "_right")).drop(columns=["_key"])
    if normalize:
        ctx.log(f"Keys normalised with '{normalize}' rules (case, spaces and punctuation ignored)")
    return ToolResult(wrap({"matched": matched, "left_only": left_only, "right_only": right_only, "joined": joined}),
                      f"{len(matched)} matched, {len(left_only)} only in left, {len(right_only)} only in right")


@tool("dedupe_rows", "Remove duplicate rows by a (normalised) column, keeping the first.", "data")
def dedupe_rows(ctx: ToolContext, table: Any, column: str, normalize: str = "text") -> ToolResult:
    df = need_df(table, "table").copy()
    df["_key"] = df[column].map(lambda v: _normalize_key(v, normalize))
    first = df.drop_duplicates("_key", keep="first")
    removed = df[df.duplicated("_key", keep="first")].copy()
    canon = dict(zip(first["_key"], first[column]))
    removed["duplicate_of"] = removed["_key"].map(canon)
    first = first.drop(columns=["_key"]).reset_index(drop=True)
    first[column] = first[column].map(lambda v: _normalize_key(v, normalize) if normalize == "text" else v)
    return ToolResult(wrap({"unique": first, "removed": removed.drop(columns=["_key"]).reset_index(drop=True)}),
                      f"{len(first)} unique, {len(removed)} duplicate(s) removed")


_AGG = {"count", "first", "sum", "mean", "max", "min", "nunique"}


@tool("aggregate", "Group rows and compute metrics. Metric spec: 'count' | 'first:col' | 'sum|mean|max|min:expr' | 'nunique:col'.", "data")
def aggregate(ctx: ToolContext, table: Any, group_by: list, metrics: dict) -> ToolResult:
    df = need_df(table, "table").copy()
    if df.empty:
        return ToolResult(pd.DataFrame(columns=[*group_by, *metrics]), "Empty table; nothing to aggregate")
    agg_spec, tmp = {}, 0
    for name, spec in metrics.items():
        fn, _, expr = str(spec).partition(":")
        if fn not in _AGG:
            raise ToolError(f"Unknown aggregation '{fn}' in metric '{name}'")
        if fn == "count":
            agg_spec[name] = (group_by[0], "size")
            continue
        if expr in df.columns:
            col = expr
        else:
            col = f"__m{tmp}"
            tmp += 1
            df[col] = row_eval(df, expr, ctx.names).values
            if fn in ("sum", "mean", "max", "min"):
                df[col] = pd.to_numeric(df[col].map(lambda v: float(v) if isinstance(v, bool) else v), errors="coerce")
        agg_spec[name] = (col, fn)
    out = df.groupby(group_by, dropna=False).agg(**agg_spec).reset_index()
    return ToolResult(out, f"{len(out)} group(s) by {', '.join(group_by)}")


@tool("sort_rows", "Sort rows by one or more columns, optionally keeping the top N.", "data")
def sort_rows(ctx: ToolContext, table: Any, by: Any, descending: bool = True, limit: int | None = None) -> ToolResult:
    df = need_df(table, "table")
    if df.empty:
        return ToolResult(df, "Empty table")
    by = by if isinstance(by, list) else [by]
    out = df.sort_values(by, ascending=not descending, kind="stable").reset_index(drop=True)
    if limit:
        out = out.head(int(limit))
    return ToolResult(out, f"Sorted by {', '.join(by)} ({'desc' if descending else 'asc'})" + (f", top {limit}" if limit else ""))


@tool("top_values", "Count the most frequent values of a column (optionally per group).", "data")
def top_values(ctx: ToolContext, table: Any, column: str, group_by: list | None = None, where: str | None = None,
               limit: int = 5) -> ToolResult:
    df = need_df(table, "table")
    if where and not df.empty:
        df = df[row_eval(df, where, ctx.names).fillna(False).astype(bool).values]
    if df.empty:
        return ToolResult(pd.DataFrame(columns=[*(group_by or []), column, "count"]), "No matching rows")
    keys = [*(group_by or []), column]
    out = df.groupby(keys).size().reset_index(name="count").sort_values("count", ascending=False).head(limit)
    return ToolResult(out.reset_index(drop=True), f"Top {len(out)} value(s) of {column}")


@tool("select_columns", "Choose, order and rename the columns of a table.", "data")
def select_columns(ctx: ToolContext, table: Any, columns: list, rename: dict | None = None) -> ToolResult:
    df = need_df(table, "table")
    present = [c for c in columns if c in df.columns]
    out = df[present].rename(columns=rename or {}).reset_index(drop=True)
    return ToolResult(out, f"Prepared {len(out)} rows with {len(present)} columns")


@tool("rank_bucket", "Label rows High/Medium/Low (or custom) by the quantile of a numeric column.", "data")
def rank_bucket(ctx: ToolContext, table: Any, column: str, into: str, buckets: dict) -> ToolResult:
    df = need_df(table, "table").copy()
    if df.empty:
        df[into] = []
        return ToolResult(df, "Empty table")
    pct = pd.to_numeric(df[column], errors="coerce").rank(pct=True)
    ordered = sorted(buckets.items(), key=lambda kv: -float(kv[1]))
    df[into] = [next((lbl for lbl, q in ordered if p >= float(q)), ordered[-1][0]) for p in pct.fillna(0)]
    counts = df[into].value_counts().to_dict()
    return ToolResult(df, "Buckets: " + ", ".join(f"{k} {v}" for k, v in counts.items()))


@tool("rule_recommendations", "Evaluate recommendation rules against each row; emit text for rules that fire.", "decision",
      raw_args=("rules",))
def rule_recommendations(ctx: ToolContext, table: Any, rules: list, key: str) -> ToolResult:
    from ..expr import TEMPLATE_RE, evaluate

    df = need_df(table, "table")
    out = []
    for rec in df.to_dict("records"):
        names = {**ctx.names, **{k: clean(v) for k, v in rec.items()}}
        for rule in rules:
            if evaluate(rule["when"], names):
                text = TEMPLATE_RE.sub(lambda m: to_text(evaluate(m.group(1), names)), rule["text"])
                out.append({key: rec.get(key), "area": rule.get("area", ""), "recommendation": text})
    res = pd.DataFrame(out, columns=[key, "area", "recommendation"])
    return ToolResult(res, f"{len(res)} recommendation(s) generated from {len(rules)} rule(s)")


@tool("export_table", "Write a table to a downloadable CSV or XLSX file.", "data")
def export_table(ctx: ToolContext, table: Any, filename: str, format: str = "csv") -> ToolResult:
    df = need_df(table, "table")
    name = re.sub(r"[^\w.-]+", "_", filename)
    if not name.endswith(f".{format}"):
        name = f"{name}.{format}"
    path = ctx.export_dir() / name
    if format == "xlsx":
        df.to_excel(path, index=False)
    else:
        df.to_csv(path, index=False)
    url = f"/api/files/{ctx.run_id}/{name}"
    return ToolResult(wrap({"url": url, "filename": name, "rows": len(df), "path": str(path)}),
                      f"Exported {len(df)} rows to {name}")


@tool("merge_record", "Combine a base record with explicit values (non-empty overrides win).", "data")
def merge_record(ctx: ToolContext, base: Any = None, overrides: dict | None = None) -> ToolResult:
    rec = dict(base or {})
    applied = []
    for k, v in (overrides or {}).items():
        if not is_missing(v):
            rec[k] = v
            applied.append(k)
    msg = f"Record has {sum(not is_missing(v) for v in rec.values())} populated field(s)"
    if applied:
        msg += f"; from request: {', '.join(applied)}"
    return ToolResult(wrap(rec), msg)


@tool("check_fields", "Check which required / optional fields of a record are present or missing.", "decision")
def check_fields(ctx: ToolContext, record: Any, required: list | None = None, optional: list | None = None) -> ToolResult:
    rec = dict(record or {})
    req, opt = required or [], optional or []
    miss_r = [f for f in req if is_missing(rec.get(f))]
    miss_o = [f for f in opt if is_missing(rec.get(f))]
    present = {f: rec.get(f) for f in [*req, *opt] if not is_missing(rec.get(f))}
    for f in miss_r:
        ctx.log(f"Required field missing: {f}", "warn")
    for f in miss_o:
        ctx.log(f"Not provided (will not be invented): {f}", "warn")
    msg = "All required fields present" if not miss_r else f"Missing required: {', '.join(miss_r)}"
    if miss_o:
        msg += f"; missing optional: {', '.join(miss_o)}"
    return ToolResult(wrap({"missing_required": miss_r, "missing_optional": miss_o, "present": present,
                            "ok": not miss_r}), msg)