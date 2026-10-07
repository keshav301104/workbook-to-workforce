"""Tool registry. A tool is a plain function registered with ``@tool``.

Plans refer to tools by name; argument names are checked against the function
signature when plans load, so a typo is caught at startup, not mid-run.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from ..config import ROOT, Settings


class ToolError(Exception):
    """Permanent, user-facing failure (bad input, missing file). Not retried."""


class TransientError(Exception):
    """Temporary failure (timeout, 503). The executor retries these."""


@dataclass
class ToolResult:
    value: Any
    summary: str = ""
    engine: str | None = None       # "llm" | "rules" for tools with an LLM path
    details: dict = field(default_factory=dict)


@dataclass
class ToolSpec:
    name: str
    fn: Callable[..., ToolResult]
    description: str
    category: str
    simulated_api: str | None = None   # name of the simulated external API, if any
    llm: bool = False
    raw_args: tuple = ()               # args holding per-row templates: passed through unrendered

    @property
    def params(self) -> dict[str, inspect.Parameter]:
        sig = inspect.signature(self.fn)
        return {n: p for n, p in sig.parameters.items() if n != "ctx"}

    def describe(self) -> dict:
        args = {}
        for n, p in self.params.items():
            args[n] = "required" if p.default is inspect.Parameter.empty else f"optional (default {p.default!r})"
        return {"name": self.name, "category": self.category, "description": self.description,
                "args": args, "llm": self.llm, "simulated_api": self.simulated_api}


TOOLS: dict[str, ToolSpec] = {}


def tool(name: str, description: str, category: str, simulated_api: str | None = None, llm: bool = False,
         raw_args: tuple = ()):
    def deco(fn: Callable[..., ToolResult]):
        TOOLS[name] = ToolSpec(name, fn, description, category, simulated_api, llm, raw_args)
        return fn

    return deco


class ToolContext:
    """What a tool can see: settings, the LLM, the run's files, a logger."""

    def __init__(self, settings: Settings, llm: Any, run_id: str, step_id: str, names: dict,
                 emit: Callable[[dict], None] | None = None):
        self.settings = settings
        self.llm = llm
        self.run_id = run_id
        self.step_id = step_id
        self.names = names            # run context (inputs, params, step outputs)
        self._emit = emit or (lambda e: None)

    def log(self, message: str, level: str = "info") -> None:
        self._emit({"type": "step_log", "step_id": self.step_id, "message": message, "level": level})

    def resolve_path(self, p: str | Path) -> Path:
        path = Path(str(p))
        if path.is_absolute():
            candidates = [path]
        else:
            candidates = [self.settings.data_dir / path, ROOT / path, self.settings.runs_dir / "uploads" / path,
                          self.settings.runs_dir / path]
        for c in candidates:
            if c.exists():
                return c
        raise ToolError(f"File not found: {p}")

    def export_dir(self) -> Path:
        d = self.settings.runs_dir / "exports" / self.run_id
        d.mkdir(parents=True, exist_ok=True)
        return d


def need_df(value: Any, arg: str) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value
    if isinstance(value, list) and (not value or isinstance(value[0], dict)):
        return pd.DataFrame(value)
    raise ToolError(f"Argument '{arg}' must be a table, got {type(value).__name__}")