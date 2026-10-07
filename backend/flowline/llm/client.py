"""Provider-agnostic LLM access.

One small interface (``structured`` / ``text``) over LangChain's
``init_chat_model`` so OpenAI, Gemini, Groq and Anthropic are a config change.
When no provider is configured — or a call fails — callers fall back to their
deterministic implementation and the UI shows that a fallback was used.
"""
from __future__ import annotations

import time
from typing import Any, TypeVar

from pydantic import BaseModel

from ..config import Settings, get_settings

T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(Exception):
    """Raised when no LLM is configured or the provider call failed."""


class LLMClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._chat = None
        self._init_error: str | None = None
        self.calls = 0
        # circuit breaker: after repeated provider failures, skip the LLM for a cool-down
        # period instead of paying a timeout on every step
        self._failures = 0
        self._open_until = 0.0
        self.breaker_threshold = 2
        self.breaker_cooldown_s = 60.0

    @property
    def enabled(self) -> bool:
        return self.settings.llm_enabled and self._init_error is None

    @property
    def label(self) -> str:
        if not self.settings.llm_enabled:
            return "Offline (deterministic fallback)"
        return f"{self.settings.provider} · {self.settings.model}"

    def _get_chat(self):
        if not self.settings.llm_enabled:
            raise LLMUnavailable("No LLM provider configured (offline mode)")
        if self._init_error:
            raise LLMUnavailable(self._init_error)
        if self._chat is None:
            try:
                from langchain.chat_models import init_chat_model

                self._chat = init_chat_model(
                    self.settings.model,
                    model_provider=self.settings.provider,
                    temperature=self.settings.temperature,
                    timeout=self.settings.llm_timeout,
                    max_retries=1,
                )
            except Exception as e:  # noqa: BLE001  (missing package, bad key format...)
                self._init_error = f"Could not initialise {self.settings.provider}: {e}"
                raise LLMUnavailable(self._init_error) from e
        return self._chat

    def _check_breaker(self) -> None:
        if time.time() < self._open_until:
            raise LLMUnavailable(f"provider failing repeatedly; skipping LLM for {int(self._open_until - time.time())}s")

    def _record(self, ok: bool) -> None:
        if ok:
            self._failures = 0
            return
        self._failures += 1
        if self._failures >= self.breaker_threshold:
            self._open_until = time.time() + self.breaker_cooldown_s
            self._failures = 0

    def structured(self, schema: type[T], system: str, user: str) -> T:
        chat = self._get_chat()
        self._check_breaker()
        t0 = time.perf_counter()
        try:
            # Tool/function calling is the structured-output method every supported provider
            # implements; older provider packages don't accept `method`, so fall back.
            try:
                runnable = chat.with_structured_output(schema, method="function_calling")
            except (TypeError, ValueError, NotImplementedError):
                runnable = chat.with_structured_output(schema)
            out = runnable.invoke([("system", system), ("human", user)])
            self._record(True)
        except Exception as e:  # noqa: BLE001
            self._record(False)
            raise LLMUnavailable(f"{type(e).__name__}: {e}") from e
        finally:
            self.calls += 1
            self.last_ms = int((time.perf_counter() - t0) * 1000)
        if out is None:
            raise LLMUnavailable("Model returned no structured output")
        if isinstance(out, dict):
            out = schema.model_validate(out)
        return out

    def text(self, system: str, user: str) -> str:
        chat = self._get_chat()
        self._check_breaker()
        try:
            msg = chat.invoke([("system", system), ("human", user)])
            self._record(True)
        except Exception as e:  # noqa: BLE001
            self._record(False)
            raise LLMUnavailable(f"{type(e).__name__}: {e}") from e
        finally:
            self.calls += 1
        content: Any = msg.content
        if isinstance(content, list):
            content = "".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
        return str(content)


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


def set_llm(client: Any) -> None:
    """Tests inject a fake client here."""
    global _client
    _client = client