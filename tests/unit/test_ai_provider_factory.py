"""LLM provider factory tests."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from stocktrace.infrastructure.ai.provider_factory import create_llm_provider
from stocktrace.infrastructure.ai.providers.claude import ClaudeProvider
from stocktrace.infrastructure.ai.providers.gemini import GeminiProvider
from stocktrace.infrastructure.ai.providers.openai_compatible import OpenAICompatibleProvider
from stocktrace.infrastructure.config.settings import AISettings


@pytest.mark.parametrize(
    ("provider_name", "expected_type"),
    [
        ("openai", OpenAICompatibleProvider),
        ("deepseek", OpenAICompatibleProvider),
        ("openrouter", OpenAICompatibleProvider),
        ("claude", ClaudeProvider),
        ("gemini", GeminiProvider),
    ],
)
def test_create_llm_provider_returns_expected_adapter(
    provider_name: str,
    expected_type: type,
) -> None:
    settings = AISettings(provider=provider_name, api_key=SecretStr("test"))
    provider = create_llm_provider(settings)
    assert isinstance(provider, expected_type)


def test_create_llm_provider_rejects_unknown_provider() -> None:
    settings = AISettings(provider="unknown", api_key=SecretStr("test"))
    with pytest.raises(ValueError, match="Unsupported AI provider"):
        create_llm_provider(settings)
