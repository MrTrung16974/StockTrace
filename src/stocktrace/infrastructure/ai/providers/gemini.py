"""Google Gemini provider using the official google-genai SDK."""

from __future__ import annotations

import time
from typing import Any

from google import genai
from google.genai import types

from stocktrace.ai.models import LLMRequest, LLMResponse
from stocktrace.infrastructure.config.settings import AISettings


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
        if api_key is None:
            msg = "STOCKTRACE_AI__API_KEY must be set when using the Gemini provider."
            raise RuntimeError(msg)
        self._client = genai.Client(api_key=api_key.get_secret_value())
        self._model = settings.model

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Generate a completion using the Gemini API."""
        config = types.GenerateContentConfig(
            temperature=request.temperature,
            max_output_tokens=request.max_tokens,
            system_instruction=request.system_prompt or None,
        )

        started = time.perf_counter()
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=request.prompt,
            config=config,
        )
        latency_ms = (time.perf_counter() - started) * 1000

        content = _extract_text(response)
        usage = response.usage_metadata

        return LLMResponse(
            content=content,
            model=self._model,
            latency_ms=latency_ms,
            prompt_tokens=_int_or_none(usage.prompt_token_count if usage else None),
            completion_tokens=_int_or_none(usage.candidates_token_count if usage else None),
        )


def _extract_text(response: Any) -> str:  # noqa: ANN401
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
