"""Google Gemini provider using the official google-genai SDK."""

from __future__ import annotations

import time
from typing import Any

from google import genai
from google.genai import types

from stocktrace.ai.models import LLMRequest, LLMResponse
from stocktrace.infrastructure.config.settings import AISettings
from stocktrace.infrastructure.logging.config import get_logger

_RETIRED_MODEL_ERROR_MARKERS = ("404", "not_found", "no longer available")
_QUOTA_ERROR_MARKERS = (
    "429",
    "resource_exhausted",
    "quota",
    "rate limit",
    "too many requests",
)


class GeminiProvider:
    """Call Google Gemini via the official google-genai SDK.

    Uses ``google.genai.Client`` which supports:
    - system_instruction (system prompt separated from user content)
    - Async generation via ``aio.models.generate_content``
    - Automatic token counting and usage metadata
    - All Gemini 2.x and 1.5 models
    """

    def __init__(self, settings: AISettings) -> None:
        self._settings = settings
        api_key = settings.api_key
        self._client = (
            genai.Client(api_key=api_key.get_secret_value()) if api_key is not None else None
        )
        self._model = settings.model
        self._fallback_model = settings.fallback_model
        self._fallback_models = settings.fallback_models
        self._logger = get_logger(__name__)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Generate a completion using the Gemini API."""
        if self._client is None:
            msg = "STOCKTRACE_AI__API_KEY must be set when using the Gemini provider."
            raise RuntimeError(msg)
        config = types.GenerateContentConfig(
            temperature=request.temperature,
            max_output_tokens=request.max_tokens,
            system_instruction=request.system_prompt or None,
        )

        started = time.perf_counter()
        models = self._model_chain()
        model, response = await self._complete_with_failover(models, request, config)
        latency_ms = (time.perf_counter() - started) * 1000

        content = _extract_text(response)
        usage = response.usage_metadata

        return LLMResponse(
            content=content,
            model=model,
            latency_ms=latency_ms,
            prompt_tokens=_int_or_none(usage.prompt_token_count if usage else None),
            completion_tokens=_int_or_none(usage.candidates_token_count if usage else None),
        )

    def _model_chain(self) -> list[str]:
        """Return configured primary and fallbacks once, retaining their priority order."""
        candidates = [self._model, self._fallback_model, *self._fallback_models]
        models: list[str] = []
        for candidate in candidates:
            normalized = candidate.strip() if candidate else ""
            if normalized and normalized not in models:
                models.append(normalized)
        return models

    async def _complete_with_failover(
        self,
        models: list[str],
        request: LLMRequest,
        config: types.GenerateContentConfig,
    ) -> tuple[str, Any]:
        """Try alternate models only for retirement and provider-quota failures."""
        for index, model in enumerate(models):
            try:
                return model, await self._generate_content(model, request, config)
            except Exception as exc:
                if not _is_model_failover_error(exc) or index == len(models) - 1:
                    raise
                self._logger.warning(
                    "gemini_model_failover",
                    failed_model=model,
                    next_model=models[index + 1],
                    reason=_model_failover_reason(exc),
                    error=str(exc),
                )
        raise RuntimeError("Gemini model failover chain was empty.")

    async def _generate_content(
        self,
        model: str,
        request: LLMRequest,
        config: types.GenerateContentConfig,
    ) -> Any:
        """Call one configured Gemini model through the async SDK."""
        client = self._client
        if client is None:
            msg = "STOCKTRACE_AI__API_KEY must be set when using the Gemini provider."
            raise RuntimeError(msg)
        return await client.aio.models.generate_content(
            model=model,
            contents=request.prompt,
            config=config,
        )


def _extract_text(response: Any) -> str:
    """Extract plain text from a Gemini GenerateContentResponse."""
    text = getattr(response, "text", None)
    if text:
        return str(text).strip()

    # Fallback: iterate candidates/parts manually
    candidates = getattr(response, "candidates", None)
    if candidates:
        parts = getattr(candidates[0].content, "parts", [])
        if parts:
            return str(parts[0].text or "").strip()

    msg = "Gemini response did not contain text content."
    raise RuntimeError(msg)


def _int_or_none(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _is_retired_model_error(error: Exception) -> bool:
    """Return whether Gemini explicitly rejected a retired model identifier."""
    message = str(error).lower()
    return "no longer available" in message and any(
        marker in message for marker in _RETIRED_MODEL_ERROR_MARKERS
    )


def _is_model_failover_error(error: Exception) -> bool:
    """Return whether another configured Gemini model may serve the request."""
    message = str(error).lower()
    is_quota_error = any(marker in message for marker in _QUOTA_ERROR_MARKERS)
    return _is_retired_model_error(error) or is_quota_error


def _model_failover_reason(error: Exception) -> str:
    """Classify a failover without leaking provider response details into event names."""
    return "retired_model" if _is_retired_model_error(error) else "quota_or_rate_limit"
