"""Factory for LLM provider adapters — Gemini only."""

from __future__ import annotations

from stocktrace.domain.ports.llm_provider import LLMProvider
from stocktrace.infrastructure.ai.providers.gemini import GeminiProvider
from stocktrace.infrastructure.config.settings import AISettings


def create_llm_provider(settings: AISettings) -> LLMProvider:
    """Create a Gemini LLM provider from settings.

    The application exclusively uses Google Gemini for all AI features.
    Configure the model and API key via environment variables:
        STOCKTRACE_AI__API_KEY=<your-gemini-api-key>
        STOCKTRACE_AI__MODEL=gemini-2.0-flash          (default)
    """
    return GeminiProvider(settings)
