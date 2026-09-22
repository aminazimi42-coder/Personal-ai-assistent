"""
services/llm_provider.py
Provider-neutral LLM boundary.

- Abstract LLMProvider base class
- OpenAIProvider adapter wrapping the OpenAI SDK client
- Provider registry: register / get / default
- Timeout, bounded retries, normalized LLMError
- Cost metadata (model, token counts) returned with each call
- Telemetry: logs model, duration, tokens for each call
"""

from __future__ import annotations

import abc
import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Normalized error
# ------------------------------------------------------------------ #

class LLMError(Exception):
    """Normalized error raised by any LLM provider."""

    def __init__(self, message: str, *, provider: str = "", cause: Exception | None = None):
        super().__init__(message)
        self.provider = provider
        self.cause = cause


# ------------------------------------------------------------------ #
# Abstract base
# ------------------------------------------------------------------ #

class LLMProvider(abc.ABC):
    """Abstract LLM provider."""

    @abc.abstractmethod
    def chat_completion(
        self,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> dict:
        """
        Run a chat completion.

        Returns dict with keys:
            content          — str (may be empty on failure)
            usage            — dict(prompt_tokens, completion_tokens, total_tokens)
            model            — str
        Raises LLMError on provider failure.
        """
        ...

    def transcribe(self, audio_path: str, model: str = "whisper-1") -> str:
        """Transcribe audio. Override in subclasses that support it."""
        raise LLMError("Transcription not supported by this provider", provider=self.__class__.__name__)


# ------------------------------------------------------------------ #
# OpenAI adapter
# ------------------------------------------------------------------ #

class OpenAIProvider(LLMProvider):
    """Adapter that wraps an OpenAI SDK client (or mock)."""

    def __init__(
        self,
        client_factory: Callable[[], Any] | None = None,
        client: Any | None = None,
        model: str = "",
        max_retries: int = 2,
        retry_delay: float = 0.5,
    ):
        self._client_factory = client_factory
        self._client = client
        self._model = model
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    def _get_client(self):
        if self._client is not None:
            return self._client
        if self._client_factory is not None:
            return self._client_factory()
        # Lazy default construction
        from openai import OpenAI
        from config import settings
        return OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.AI_REQUEST_TIMEOUT,
        )

    # -- chat completion ------------------------------------------------ #

    def chat_completion(
        self,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> dict:
        last_err: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            t0 = time.monotonic()
            try:
                client = self._get_client()
                response = client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                usage_obj = getattr(response, "usage", None)
                usage = {
                    "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0) or 0,
                    "completion_tokens": getattr(usage_obj, "completion_tokens", 0) or 0,
                    "total_tokens": getattr(usage_obj, "total_tokens", 0) or 0,
                }
                raw = ""
                if response.choices:
                    raw = getattr(response.choices[0].message, "content", "") or ""
                duration_ms = round((time.monotonic() - t0) * 1000)
                logger.info(
                    "llm chat_completion",
                    extra={
                        "provider": "openai",
                        "model": self._model,
                        "duration_ms": duration_ms,
                        "attempt": attempt,
                        **usage,
                    },
                )
                return {
                    "content": raw,
                    "usage": usage,
                    "model": self._model,
                }
            except Exception as exc:
                last_err = exc
                duration_ms = round((time.monotonic() - t0) * 1000)
                logger.warning(
                    "llm chat_completion attempt failed",
                    extra={
                        "provider": "openai",
                        "model": self._model,
                        "attempt": attempt,
                        "duration_ms": duration_ms,
                        "error": str(exc),
                    },
                    exc_info=True,
                )
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay * attempt)
        raise LLMError(
            f"OpenAI chat completion failed after {self._max_retries} attempts: {last_err}",
            provider="openai",
            cause=last_err,
        )

    # -- transcription -------------------------------------------------- #

    def transcribe(self, audio_path: str, model: str = "whisper-1") -> str:
        try:
            import config.settings as settings
            client = self._get_client()
            with open(audio_path, "rb") as audio:
                transcription = client.audio.transcriptions.create(
                    model=model,
                    file=audio,
                    timeout=getattr(settings, "AI_REQUEST_TIMEOUT", 30),
                )
            return str(getattr(transcription, "text", "")).strip()
        except Exception as exc:
            raise LLMError(f"Transcription failed: {exc}", provider="openai", cause=exc)


# ------------------------------------------------------------------ #
# Registry
# ------------------------------------------------------------------ #

_registry: dict[str, LLMProvider] = {}
_default_provider_name: str | None = None


def register_provider(name: str, provider: LLMProvider) -> None:
    """Register a provider under *name*."""
    _registry[name] = provider


def get_provider(name: str) -> LLMProvider:
    """Return a previously-registered provider. Raises LLMError if missing."""
    if name not in _registry:
        raise LLMError(f"No LLM provider registered as '{name}'", provider="registry")
    return _registry[name]


def set_default_provider(name: str) -> None:
    """Set the default provider name (used by get_default_provider)."""
    global _default_provider_name
    _default_provider_name = name


def get_default_provider() -> LLMProvider:
    """Return the default provider, selected from settings.OPENAI_CHAT_MODEL."""
    global _default_provider_name
    if _default_provider_name is None:
        # Default to 'openai' — driven by OPENAI_CHAT_MODEL in settings
        _default_provider_name = "openai"
    if _default_provider_name not in _registry:
        raise LLMError(
            f"Default provider '{_default_provider_name}' is not registered",
            provider="registry",
        )
    return _registry[_default_provider_name]


def _ensure_default_registered() -> None:
    """Lazy-register the OpenAI provider on first access."""
    if "openai" not in _registry:
        from config import settings
        register_provider("openai", OpenAIProvider(model=settings.OPENAI_CHAT_MODEL))


def get_llm_provider() -> LLMProvider:
    """Convenience: ensure default is registered, then return it."""
    _ensure_default_registered()
    return get_default_provider()
