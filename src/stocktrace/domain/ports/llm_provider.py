"""LLM provider port."""

from __future__ import annotations

from typing import Protocol

from stocktrace.ai.models import LLMRequest, LLMResponse


class LLMProvider(Protocol):
    """Outbound port for large language model completion."""

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Return model completion for a normalized request."""
        ...
