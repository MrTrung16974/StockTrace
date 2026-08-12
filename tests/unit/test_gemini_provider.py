"""Gemini provider tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from stocktrace.ai.models import LLMRequest
from stocktrace.infrastructure.ai.providers.gemini import GeminiProvider
from stocktrace.infrastructure.config.settings import AISettings

_FALLBACK_ATTEMPTS = 2


@pytest.mark.asyncio
async def test_gemini_provider_retries_with_fallback_for_retired_model() -> None:
    provider = GeminiProvider(
        AISettings(
            api_key=SecretStr("test-key"),
            model="gemini-2.0-flash-lite",
            fallback_model="gemini-2.5-flash",
        ),
    )
    generate_content = AsyncMock(
        side_effect=[
            RuntimeError("404 NOT_FOUND: model is no longer available"),
            SimpleNamespace(text="Phân tích thị trường", usage_metadata=None),
        ],
    )
    provider._client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)),
    )

    response = await provider.complete(LLMRequest(prompt="Dữ liệu thị trường"))

    assert response.content == "Phân tích thị trường"
    assert response.model == "gemini-2.5-flash"
    assert [call.kwargs["model"] for call in generate_content.await_args_list] == [
        "gemini-2.0-flash-lite",
        "gemini-2.5-flash",
    ]


@pytest.mark.asyncio
async def test_gemini_provider_does_not_mask_authentication_errors() -> None:
    provider = GeminiProvider(AISettings(api_key=SecretStr("test-key")))
    generate_content = AsyncMock(side_effect=RuntimeError("403 permission denied"))
    provider._client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)),
    )

    with pytest.raises(RuntimeError, match="permission denied"):
        await provider.complete(LLMRequest(prompt="Dữ liệu thị trường"))

    generate_content.assert_awaited_once()


@pytest.mark.asyncio
async def test_gemini_provider_uses_next_model_when_quota_is_exhausted() -> None:
    provider = GeminiProvider(
        AISettings(
            api_key=SecretStr("test-key"),
            model="gemini-2.5-flash",
            fallback_model=None,
            fallback_models=["gemini-2.5-flash-lite", "gemini-2.5-pro"],
        ),
    )
    generate_content = AsyncMock(
        side_effect=[
            RuntimeError("429 RESOURCE_EXHAUSTED: quota exhausted"),
            SimpleNamespace(text="Đã phân tích bằng fallback", usage_metadata=None),
        ],
    )
    provider._client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)),
    )

    response = await provider.complete(LLMRequest(prompt="Dữ liệu thị trường"))

    assert response.model == "gemini-2.5-flash-lite"
    assert [call.kwargs["model"] for call in generate_content.await_args_list] == [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ]


@pytest.mark.asyncio
async def test_gemini_provider_raises_after_all_quota_fallbacks_fail() -> None:
    provider = GeminiProvider(
        AISettings(
            api_key=SecretStr("test-key"),
            fallback_model=None,
            fallback_models=["gemini-2.5-flash-lite"],
        ),
    )
    generate_content = AsyncMock(side_effect=RuntimeError("429 quota exhausted"))
    provider._client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)),
    )

    with pytest.raises(RuntimeError, match="quota exhausted"):
        await provider.complete(LLMRequest(prompt="Dữ liệu thị trường"))

    assert generate_content.await_count == _FALLBACK_ATTEMPTS
