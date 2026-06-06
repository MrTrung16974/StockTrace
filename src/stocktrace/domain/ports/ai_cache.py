"""AI cache port."""

from __future__ import annotations

from typing import Protocol


class AICache(Protocol):
    """Port for caching AI responses and translations."""

    async def get(self, key: str) -> str | None:
        """Return a cached JSON payload if present."""

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Cache a JSON payload for a limited time."""

    async def close(self) -> None:
        """Release cache resources if needed."""
