"""In-memory AI response cache."""

from __future__ import annotations

from time import monotonic


class InMemoryAICache:
    """Process-local AI cache with TTL support."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, str]] = {}

    async def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at <= monotonic():
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._store[key] = (monotonic() + ttl_seconds, value)

    async def close(self) -> None:
        self._store.clear()
