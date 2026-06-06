"""Anthropic Claude messages API provider."""

from __future__ import annotations

import time
from typing import Any

import httpx

from stocktrace.ai.models import LLMRequest, LLMResponse
from stocktrace.infrastructure.config.settings import AISettings

_CLAUDE_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"


class ClaudeProvider:
    """Call Anthropic Claude messages endpoint."""

    def __init__(self, settings: AISettings) -> None:
        self._settings = settings
        self._timeout = settings.request_timeout_seconds

    async def complete(self, request: LLMRequest) -> LLMResponse:
        api_key = self._settings.api_key
        if api_key is None:
            msg = "AI API key is not configured."
            raise RuntimeError(msg)

        payload: dict[str, Any] = {
            "model": self._settings.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt

        headers = {
            "x-api-key": api_key.get_secret_value(),
            "anthropic-version": _ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(_CLAUDE_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        latency_ms = (time.perf_counter() - started) * 1000
        content_blocks = data.get("content")
        if not isinstance(content_blocks, list) or not content_blocks:
            msg = "Claude response did not contain content."
            raise RuntimeError(msg)

        content = str(content_blocks[0].get("text") or "").strip()
        if not content:
            msg = "Claude response content was empty."
            raise RuntimeError(msg)

        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            model=str(data.get("model") or self._settings.model),
            latency_ms=latency_ms,
            prompt_tokens=_int_or_none(usage.get("input_tokens")),
            completion_tokens=_int_or_none(usage.get("output_tokens")),
        )


def _int_or_none(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None
