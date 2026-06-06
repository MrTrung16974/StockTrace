"""OpenAI-compatible chat completion provider."""

from __future__ import annotations

import time
from typing import Any

import httpx

from stocktrace.ai.models import LLMRequest, LLMResponse
from stocktrace.infrastructure.config.settings import AISettings


class OpenAICompatibleProvider:
    """Call OpenAI-style /v1/chat/completions endpoints."""

    def __init__(self, settings: AISettings, base_url: str | None = None) -> None:
        self._settings = settings
        self._base_url = (base_url or settings.resolved_base_url).rstrip("/")
        self._timeout = settings.request_timeout_seconds

    async def complete(self, request: LLMRequest) -> LLMResponse:
        api_key = self._settings.api_key
        if api_key is None:
            msg = "AI API key is not configured."
            raise RuntimeError(msg)

        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": self._settings.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        latency_ms = (time.perf_counter() - started) * 1000
        return _to_llm_response(data, latency_ms=latency_ms, model=self._settings.model)


def _to_llm_response(payload: dict[str, Any], latency_ms: float, model: str) -> LLMResponse:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        msg = "LLM response did not contain choices."
        raise RuntimeError(msg)

    message = choices[0].get("message", {})
    content = str(message.get("content") or "").strip()
    if not content:
        msg = "LLM response content was empty."
        raise RuntimeError(msg)

    usage = payload.get("usage", {})
    return LLMResponse(
        content=content,
        model=str(payload.get("model") or model),
        latency_ms=latency_ms,
        prompt_tokens=_int_or_none(usage.get("prompt_tokens")),
        completion_tokens=_int_or_none(usage.get("completion_tokens")),
    )


def _int_or_none(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None
