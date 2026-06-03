"""Yahoo Finance RSS news provider."""

from __future__ import annotations

from datetime import UTC, datetime
from time import struct_time
from typing import Any, cast

import feedparser
import httpx

from stocktrace.application.services.market_data import MarketDataError, NewsArticle


class YahooFinanceNewsProvider:
    """Retrieve latest related news from Yahoo Finance RSS."""

    _feed_url = "https://feeds.finance.yahoo.com/rss/2.0/headline"

    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds

    async def get_news(self, symbol: str, limit: int) -> list[NewsArticle]:
        """Return latest news articles for a symbol."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(
                    self._feed_url,
                    params={"s": symbol, "region": "US", "lang": "en-US"},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            msg = f"Could not retrieve news for {symbol}."
            raise MarketDataError(msg) from exc

        parsed = feedparser.parse(response.text)
        entries = cast(list[dict[str, Any]], parsed.entries)
        articles: list[NewsArticle] = []
        for entry in entries[:limit]:
            title = str(entry.get("title") or "").strip()
            url = str(entry.get("link") or "").strip()
            summary = str(entry.get("summary") or entry.get("description") or "").strip() or None
            if not title or not url:
                continue
            articles.append(
                NewsArticle(
                    ticker=symbol,
                    title=title,
                    summary=summary,
                    url=url,
                    source=str(entry.get("source") or "Yahoo Finance"),
                    published_at=_published_at(entry.get("published_parsed")),
                ),
            )
        return articles


def _published_at(value: object) -> datetime | None:
    if not isinstance(value, struct_time):
        return None
    return datetime(*value[:6], tzinfo=UTC)
