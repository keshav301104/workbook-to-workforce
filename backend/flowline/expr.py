"""Safe expression + template evaluation used by plans.

Plans never contain Python. They contain small expressions such as
``current_stock < minimum_stock`` or ``len(restock_list) == 0`` and templates
such as ``"Found {{ len(rows) }} products"``.  They are evaluated with
``simpleeval`` (no imports, no dunder access, no arbitrary calls), so a plan
drafted by an LLM for a new workflow cannot execute code.

Reference syntax inside plan args:
  "$name.path"        -> the object stored in the run context (DataFrame, dict, ...)
  "{{ expression }}"  -> evaluated; typed when it is the whole string, text otherwise
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any, Iterable

import pandas as pd
from simpleeval import EvalWithCompoundTypes, NameNotDefined

REF_RE = re.compile(r"^\$([A-Za-z_][\w]*(?:\.[\w]+)*)$")
TEMPLATE_RE = re.compile(r"\{\{\s*(.+?)\s*\}\}", re.S)


class ExpressionError(Exception):
    pass


class AttrDict(dict):
    """dict that also allows ``obj.key`` access in expressions (missing -> None)."""

    def __getattribute__(self, item: str) -> Any:
        # data keys win over dict methods, so a column called `items` or `values` works
        if not item.startswith("_") and dict.__contains__(self, item):
            return dict.__getitem__(self, item)
        return super().__getattribute__(item)

    def __getattr__(self, item: str) -> Any:
        if item.startswith("_"):
            raise AttributeError(item)
        return None


def wrap(value: Any) -> Any:
    if isinstance(value, dict) and not isinstance(value, AttrDict):
        return AttrDict({k: wrap(v) for k, v in value.items()})
    return value


def is_missing(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    if v is pd.NA or v is pd.NaT:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    if isinstance(v, (list, tuple, set, dict)) and len(v) == 0:
        return True
    if isinstance(v, pd.DataFrame):
        return v.empty
    return False


def clean(v: Any) -> Any:
    """Normalise pandas scalars (NaN/NA/numpy types) into plain Python values."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(v, "item") and not isinstance(v, (list, dict, str)):
        try:
            return v.item()
        except Exception:  # noqa: BLE001
            return v
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.strftime("%Y-%m-%d")
    return v


def as_list(v: Any) -> list:
    if is_missing(v):
        return []
    if isinstance(v, pd.Series):
        return [clean(x) for x in v.tolist() if not is_missing(x)]
    if isinstance(v, str):
        return [p.strip() for p in re.split(r"[;,\n]", v) if p.strip()]
    if isinstance(v, Iterable) and not isinstance(v, dict):
        return [x for x in v if not is_missing(x)]
    return [v]


# ----------------------------------------------------------------------------- helper functions
def _join(items: Any, sep: str = ", ") -> str:
    return sep.join(str(clean(x)) for x in as_list(items))


def _unique(table: pd.DataFrame, column: str) -> list:
    if table is None or column not in getattr(table, "columns", []):
        return []
    return [clean(x) for x in table[column].dropna().unique().tolist() if not is_missing(x)]


def _col(table: pd.DataFrame, column: str) -> list:
    if table is None or column not in getattr(table, "columns", []):
        return []
    return [clean(x) for x in table[column].tolist()]


def _first(table: Any) -> Any:
    if isinstance(table, pd.DataFrame):
        return None if table.empty else AttrDict({k: clean(v) for k, v in table.iloc[0].to_dict().items()})
    lst = as_list(table)
    return lst[0] if lst else None


def _records(table: pd.DataFrame, limit: int | None = None) -> list:
    if not isinstance(table, pd.DataFrame):
        return []
    df = table if limit is None else table.head(limit)
    return [AttrDict({k: clean(v) for k, v in r.items()}) for r in df.to_dict("records")]


def _pct(x: Any, digits: int = 1) -> str:
    if is_missing(x):
        return "—"
    return f"{float(x):.{digits}f}%"


def _money(x: Any, symbol: str = "$") -> str:
    if is_missing(x):
        return "—"
    return f"{symbol}{float(x):,.2f}"


def _num(x: Any, digits: int = 0) -> str:
    if is_missing(x):
        return "—"
    return f"{float(x):,.{digits}f}"


def _slug(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")


def _keyword_label(text: Any, mapping: dict, default: Any = None) -> Any:
    """Return the first label whose keyword list matches the text (word-ish match)."""
    t = f" {str(text or '').lower()} "
    for label, words in mapping.items():
        for w in as_list(words):
            if re.search(rf"(?<![a-z0-9]){re.escape(str(w).lower())}(?![a-z0-9])", t):
                return label
    return default


def _split(text: Any, sep: str = ";") -> list:
    if is_missing(text):
        return []
    if isinstance(text, (list, tuple)):
        return [str(x).strip() for x in text]
    return [p.strip() for p in str(text).split(sep) if p.strip()]


def _norm_set(items: Any) -> set:
    return {str(x).strip().lower() for x in as_list(items)}


def _overlap(have: Any, need: Any) -> float:
    """Share of ``need`` items present in ``have`` (0..1). Empty need -> 1."""
    n = _norm_set(need)
    if not n:
        return 1.0
    return round(len(n & _norm_set(have)) / len(n), 4)


def _matched(have: Any, need: Any) -> list:
    h = _norm_set(have)
    return [x for x in as_list(need) if str(x).strip().lower() in h]


def _missing_items(have: Any, need: Any) -> list:
    h = _norm_set(have)
    return [x for x in as_list(need) if str(x).strip().lower() not in h]


def _coalesce(*args: Any) -> Any:
    for a in args:
        if not is_missing(a):
            return a
    return None


WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _to_date(x: Any) -> date | None:
    """Parse ISO dates, 'Oct 20', 'October 20, 2026', 'today', 'tomorrow', 'friday'.
    A date given without a year means its next occurrence."""
    if is_missing(x):
        return None
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    from datetime import timedelta

    from dateutil import parser as dparser

    s = str(x).strip().lower().replace("next ", "")
    today = date.today()
    if s == "today":
        return today
    if s == "tomorrow":
        return today + timedelta(days=1)
    if s in WEEKDAYS:
        return today + timedelta(days=(WEEKDAYS.index(s) - today.weekday() - 1) % 7 + 1)
    try:
        d = dparser.parse(str(x), default=datetime(today.year, today.month, today.day)).date()
    except (ValueError, OverflowError):
        return None
    if not re.search(r"\b\d{4}\b", str(x)) and d < today - timedelta(days=60):
        d = d.replace(year=d.year + 1)
    return d


def _days_between(a: Any, b: Any) -> int | None:
    da, db = _to_date(a), _to_date(b)
    if da is None or db is None:
        return None
    return (db - da).days


def _fmt_date(x: Any, fmt: str = "%b %d, %Y") -> str:
    d = _to_date(x)
    return d.strftime(fmt) if d else "—"


def _plural(n: Any, word: str, plural: str | None = None) -> str:
    n = int(n or 0)
    return f"{n} {word if n == 1 else (plural or word + 's')}"


def _count(table: Any, expr: str | None = None, names: dict | None = None) -> int:
    if not isinstance(table, pd.DataFrame):
        return len(as_list(table))
    if expr is None or table.empty:
        return len(table)
    return int(row_eval(table, expr, names or {}).fillna(False).astype(bool).sum())


def _norm_key(v: Any) -> str | None:
    return None if is_missing(v) else re.sub(r"[^A-Z0-9]", "", str(v).upper())


def _norm_text(v: Any) -> str | None:
    return None if is_missing(v) else re.sub(r"[^a-z0-9]+", " ", str(v).lower()).strip()


def _vocab(table: Any, column: str, sep: str = ";") -> list:
    seen: dict[str, str] = {}
    for v in _col(table, column):
        for part in _split(v, sep):
            seen.setdefault(part.lower(), part)
    return sorted(seen.values(), key=str.lower)


def _lookup_value(table: Any, key_column: str, key: Any, value_column: str, default: Any = None) -> Any:
    if not isinstance(table, pd.DataFrame) or table.empty or key_column not in table.columns:
        return default
    hit = table[table[key_column] == key]
    return default if hit.empty else clean(hit.iloc[0][value_column])


def _where(table: Any, expr: str, names: dict | None = None) -> pd.DataFrame:
    if not isinstance(table, pd.DataFrame) or table.empty:
        return table
    return table[row_eval(table, expr, names or {}).fillna(False).astype(bool).values].reset_index(drop=True)


def _filter_eq(table: Any, column: str, value: Any) -> pd.DataFrame:
    if not isinstance(table, pd.DataFrame) or table.empty:
        return table
    return table[table[column] == value].reset_index(drop=True)


def _filename(path: Any) -> str:
    """Display name of a file path (drops folders and the upload id prefix)."""
    return "" if is_missing(path) else str(path).replace("\\", "/").split("/")[-1].split("__", 1)[-1]


def _fuzzy_in(query: Any, text: Any, threshold: int = 85) -> bool:
    """True when query (e.g. 'wool beanies') loosely appears in text (e.g. 'Wool Beanie')."""
    if is_missing(query) or is_missing(text):
        return False
    from rapidfuzz import fuzz

    return fuzz.partial_ratio(str(query).lower().rstrip("s"), str(text).lower()) >= threshold


FUNCTIONS = {
    "len": lambda x: 0 if x is None else len(x),
    "min": min, "max": max, "round": round, "abs": abs, "sum": sum, "sorted": sorted,
    "int": int, "float": float, "str": str, "bool": bool, "list": list, "any": any, "all": all,
    "join": _join, "unique": _unique, "col": _col, "first": _first, "records": _records,
    "pct": _pct, "money": _money, "num": _num, "slug": _slug, "keyword_label": _keyword_label,
    "split": _split, "overlap": _overlap, "matched": _matched, "missing_items": _missing_items,
    "coalesce": _coalesce, "days_between": _days_between, "fmt_date": _fmt_date, "to_date": _to_date,
    "plural": _plural, "count": _count, "missing": is_missing, "exists": lambda x: not is_missing(x),
    "lower": lambda s: str(s or "").lower(), "upper": lambda s: str(s or "").upper(),
    "title": lambda s: str(s or "").title(),
    "today": lambda: date.today().isoformat(),
    "sqrt": math.sqrt, "log10": math.log10,
    "filename": _filename, "fuzzy_in": _fuzzy_in, "where": _where, "filter_eq": _filter_eq,
    "norm_key": _norm_key, "norm_text": _norm_text, "vocab": _vocab, "lookup_value": _lookup_value,
}


def _evaluator(names: dict) -> EvalWithCompoundTypes:
    # count()/where() evaluate row expressions that may reference run context (params, inputs)
    fns = {**FUNCTIONS,
           "count": lambda t, e=None: _count(t, e, names),
           "where": lambda t, e: _where(t, e, names)}
    return EvalWithCompoundTypes(functions=fns, names=names)


def evaluate(expr: str, names: dict) -> Any:
    try:
        return _evaluator(names).eval(expr)
    except NameNotDefined as e:
        raise ExpressionError(f"Unknown name in expression `{expr}`: {e}") from e
    except Exception as e:  # noqa: BLE001
        raise ExpressionError(f"Could not evaluate `{expr}`: {e}") from e


def lookup_path(names: dict, path: str) -> Any:
    parts = path.split(".")
    if parts[0] not in names:
        raise ExpressionError(f"Unknown reference ${path}")
    cur = names[parts[0]]
    for p in parts[1:]:
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            cur = getattr(cur, p, None)
    return cur


def to_text(v: Any) -> str:
    v = clean(v)
    if v is None:
        return ""
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else f"{v:,.2f}"
    if isinstance(v, (list, tuple)):
        return ", ".join(to_text(x) for x in v)
    return str(v)


def render(value: Any, names: dict) -> Any:
    """Resolve $refs and {{ }} templates recursively inside plan values."""
    if isinstance(value, str):
        s = value.strip()
        m = REF_RE.match(s)
        if m:
            return lookup_path(names, m.group(1))
        full = TEMPLATE_RE.fullmatch(s) if s.count("{{") == 1 else None
        if full:
            return evaluate(full.group(1), names)
        if TEMPLATE_RE.search(value):
            return TEMPLATE_RE.sub(lambda mm: to_text(evaluate(mm.group(1), names)), value)
        return value
    if isinstance(value, dict):
        return {k: render(v, names) for k, v in value.items()}
    if isinstance(value, list):
        return [render(v, names) for v in value]
    return value


def row_eval(df: pd.DataFrame, expr: str, context: dict) -> pd.Series:
    """Evaluate an expression once per row; row columns shadow context names."""
    ev = _evaluator({})
    out = []
    for rec in df.to_dict("records"):
        names = dict(context)
        names.update({k: clean(v) for k, v in rec.items()})
        ev.names = names
        try:
            out.append(ev.eval(expr))
        except NameNotDefined as e:
            raise ExpressionError(f"Unknown column or name in `{expr}`: {e}") from e
        except Exception as e:  # noqa: BLE001
            raise ExpressionError(f"Could not evaluate `{expr}` on row {rec}: {e}") from e
    return pd.Series(out, index=df.index, dtype=object)