"""LLM provider factory tests."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from stocktrace.infrastructure.ai.provider_factory import create_llm_provider
from stocktrace.infrastructure.ai.providers.gemini import GeminiProvider
from stocktrace.infrastructure.config.settings import AISettings


def test_create_llm_provider_returns_gemini() -> None:
    settings = AISettings(provider="gemini", api_key=SecretStr("test"))
    provider = create_llm_provider(settings)
    assert isinstance(provider, GeminiProvider)
