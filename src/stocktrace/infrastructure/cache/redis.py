"""Redis-backed market data cache."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal

import redis.asyncio as redis

from stocktrace.application.services.market_data import NewsArticle, StockQuote
from stocktrace.domain.ports.market_data_cache import MarketDataCache


class RedisMarketDataCache(MarketDataCache):
    """Redis cache for quotes and news articles."""

    def __init__(self, url: str) -> None:
        self._client = redis.from_url(url, decode_responses=True)

    async def get_quote(self, ticker: str) -> StockQuote | None:
        value = await self._client.get(_quote_key(ticker))
        if value is None:
            return None
        return _quote_from_dict(json.loads(value))

    async def set_quote(self, quote: StockQuote, ttl_seconds: int) -> None:
        await self._client.set(_quote_key(quote.ticker), json.dumps(_quote_to_dict(quote)), ex=ttl_seconds)

    async def get_news(self, ticker: str, limit: int) -> list[NewsArticle] | None:
        value = await self._client.get(_news_key(ticker, limit))
        if value is None:
            return None
        return [_news_from_dict(item) for item in json.loads(value)]

    async def set_news(
        self,
        ticker: str,
        limit: int,
        articles: list[NewsArticle],
        ttl_seconds: int,
    ) -> None:
        payload = [_news_to_dict(article) for article in articles]
        await self._client.set(_news_key(ticker, limit), json.dumps(payload), ex=ttl_seconds)

    async def close(self) -> None:
        await self._client.aclose()


def _quote_key(ticker: str) -> str:
    return f"stocktrace:quote:{ticker.upper()}"


def _news_key(ticker: str, limit: int) -> str:
    return f"stocktrace:news:{ticker.upper()}:{limit}"


def _quote_to_dict(quote: StockQuote) -> dict[str, object]:
    payload = asdict(quote)
    payload["timestamp"] = quote.timestamp.isoformat()
    payload["current_price"] = float(quote.current_price)
    payload["change"] = float(quote.change)
    payload["change_percent"] = float(quote.change_percent)
    payload["open_price"] = float(quote.open_price)
    payload["high_price"] = float(quote.high_price)
    payload["low_price"] = float(quote.low_price)
    return payload


def _quote_from_dict(payload: dict[str, object]) -> StockQuote:
    return StockQuote(
        ticker=str(payload["ticker"]),
        company_name=str(payload["company_name"]),
        current_price=Decimal(str(payload["current_price"])),
        change=Decimal(str(payload["change"])),
        change_percent=Decimal(str(payload["change_percent"])),
        open_price=Decimal(str(payload["open_price"])),
        high_price=Decimal(str(payload["high_price"])),
        low_price=Decimal(str(payload["low_price"])),
        volume=int(payload["volume"]),
        timestamp=datetime.fromisoformat(str(payload["timestamp"])),
        currency=str(payload.get("currency", "USD")),
        source=str(payload.get("source", "Yahoo Finance")),
    )


def _news_to_dict(article: NewsArticle) -> dict[str, object]:
    payload = asdict(article)
    payload["published_at"] = article.published_at.isoformat() if article.published_at else None
    return payload


def _news_from_dict(payload: dict[str, object]) -> NewsArticle:
    published_at = payload.get("published_at")
    return NewsArticle(
        ticker=str(payload["ticker"]),
        title=str(payload["title"]),
        summary=str(payload["summary"]) if payload.get("summary") is not None else None,
        url=str(payload["url"]),
        source=str(payload.get("source", "Yahoo Finance")),
        published_at=datetime.fromisoformat(str(published_at)) if published_at else None,
    )
