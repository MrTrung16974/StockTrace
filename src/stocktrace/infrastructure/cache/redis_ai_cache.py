"""Redis-backed AI response cache."""

from __future__ import annotations

import redis.asyncio as redis


class RedisAICache:
    """Redis cache for AI analysis and translation payloads."""

    def __init__(self, url: str) -> None:
        self._client = redis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        return await self._client.get(_redis_key(key))

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        await self._client.set(_redis_key(key), value, ex=ttl_seconds)

    async def close(self) -> None:
        await self._client.aclose()


def _redis_key(key: str) -> str:
    return f"stocktrace:ai:{key}"
