"""Factory for LLM provider adapters."""

from __future__ import annotations

from stocktrace.domain.ports.llm_provider import LLMProvider
from stocktrace.infrastructure.ai.providers.claude import ClaudeProvider
from stocktrace.infrastructure.ai.providers.gemini import GeminiProvider
from stocktrace.infrastructure.ai.providers.openai_compatible import OpenAICompatibleProvider
from stocktrace.infrastructure.config.settings import AISettings

_DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


def create_llm_provider(settings: AISettings) -> LLMProvider:
    """Create an LLM provider from settings."""
    provider = settings.provider.lower().strip()
    if provider == "claude":
        return ClaudeProvider(settings)
    if provider == "gemini":
        return GeminiProvider(settings)
    if provider in _DEFAULT_BASE_URLS:
        return OpenAICompatibleProvider(settings, base_url=_DEFAULT_BASE_URLS[provider])
    if settings.base_url:
        return OpenAICompatibleProvider(settings, base_url=settings.base_url)
    msg = f"Unsupported AI provider: {settings.provider}"
    raise ValueError(msg)
