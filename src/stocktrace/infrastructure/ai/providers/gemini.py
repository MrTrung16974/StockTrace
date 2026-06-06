"""Google Gemini generateContent provider."""

from __future__ import annotations

import time
from typing import Any

import httpx

from stocktrace.ai.models import LLMRequest, LLMResponse
from stocktrace.infrastructure.config.settings import AISettings

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider:
    """Call Google Gemini generateContent endpoint."""

    def __init__(self, settings: AISettings) -> None:
        self._settings = settings
        self._timeout = settings.request_timeout_seconds

    async def complete(self, request: LLMRequest) -> LLMResponse:
        api_key = self._settings.api_key
        if api_key is None:
            msg = "AI API key is not configured."
            raise RuntimeError(msg)

        prompt = request.prompt
        if request.system_prompt:
            prompt = f"{request.system_prompt}\n\n{prompt}"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }
        model = self._settings.model
        url = f"{_GEMINI_BASE}/{model}:generateContent"

        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                url,
                params={"key": api_key.get_secret_value()},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        latency_ms = (time.perf_counter() - started) * 1000
        content = _extract_gemini_text(data)
        usage = data.get("usageMetadata", {})
        return LLMResponse(
            content=content,
            model=model,
            latency_ms=latency_ms,
            prompt_tokens=_int_or_none(usage.get("promptTokenCount")),
            completion_tokens=_int_or_none(usage.get("candidatesTokenCount")),
        )


def _extract_gemini_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        msg = "Gemini response did not contain candidates."
        raise RuntimeError(msg)

    content = candidates[0].get("content", {})
    parts = content.get("parts")
    if not isinstance(parts, list) or not parts:
        msg = "Gemini response did not contain parts."
        raise RuntimeError(msg)

    text = str(parts[0].get("text") or "").strip()
    if not text:
        msg = "Gemini response content was empty."
        raise RuntimeError(msg)
    return text


def _int_or_none(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None
