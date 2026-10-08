"""Runtime settings, read from environment / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# provider -> (env var holding the key, default model)
PROVIDERS: dict[str, tuple[str, str]] = {
    "openai": ("OPENAI_API_KEY", "gpt-4.1-mini"),
    "google_genai": ("GOOGLE_API_KEY", "gemini-2.5-flash"),
    "groq": ("GROQ_API_KEY", "openai/gpt-oss-120b"),
    "anthropic": ("ANTHROPIC_API_KEY", "claude-haiku-4-5"),
}
PROVIDER_ALIASES = {"gemini": "google_genai", "google": "google_genai", "claude": "anthropic"}


def _resolve_provider() -> tuple[str, str]:
    raw = os.getenv("LLM_PROVIDER", "auto").strip().lower()
    raw = PROVIDER_ALIASES.get(raw, raw)
    if raw == "offline":
        return "offline", ""
    if raw == "auto":
        for name, (key_env, _) in PROVIDERS.items():
            if os.getenv(key_env):
                raw = name
                break
        else:
            return "offline", ""
    if raw not in PROVIDERS:
        raise ValueError(f"Unknown LLM_PROVIDER '{raw}'. Use one of: auto, offline, {', '.join(PROVIDERS)}")
    model = os.getenv("LLM_MODEL") or PROVIDERS[raw][1]
    return raw, model


def _path(env: str, default: str) -> Path:
    p = Path(os.getenv(env, default))
    return p if p.is_absolute() else ROOT / p


@dataclass
class Settings:
    workflow_file: Path = field(default_factory=lambda: _path("WORKFLOW_FILE", "workflows/AI_Agent_Workflow_Assessment_1.xlsx"))
    plans_dir: Path = field(default_factory=lambda: _path("PLANS_DIR", "workflows/plans"))
    data_dir: Path = field(default_factory=lambda: _path("DATA_DIR", "data"))
    runs_dir: Path = field(default_factory=lambda: _path("RUNS_DIR", "runs"))
    provider: str = ""
    model: str = ""
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    llm_timeout: float = float(os.getenv("LLM_TIMEOUT", "45"))
    # Router: below this confidence the agent asks which workflow was meant.
    router_min_confidence: float = float(os.getenv("ROUTER_MIN_CONFIDENCE", "0.55"))
    # Simulated external APIs (orders, shipments, employee directory)
    api_latency_ms: int = int(os.getenv("SIM_API_LATENCY_MS", "250"))
    fault_rate: float = float(os.getenv("SIM_FAULT_RATE", "0"))
    # Which frontend addresses may call this API (the frontend runs as a separate app)
    cors_origins: list[str] = field(default_factory=lambda: [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500").split(",") if o.strip()])

    def __post_init__(self) -> None:
        if not self.provider:
            self.provider, self.model = _resolve_provider()
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        (self.runs_dir / "uploads").mkdir(exist_ok=True)
        (self.runs_dir / "exports").mkdir(exist_ok=True)

    @property
    def llm_enabled(self) -> bool:
        return self.provider != "offline"

    @property
    def live_log_file(self) -> Path:
        return self.runs_dir / "execution_log.csv"

    @property
    def history_file(self) -> Path:
        return self.runs_dir / "history.jsonl"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def set_settings(s: Settings) -> None:
    """Used by tests to point the engine at temporary directories."""
    global _settings
    _settings = s