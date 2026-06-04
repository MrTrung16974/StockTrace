"""Yahoo Finance RSS news provider."""

from __future__ import annotations

from datetime import UTC, datetime
from time import struct_time
from typing import Any, cast

import feedparser
import httpx

from stocktrace.application.services.market_data import NewsArticle
from stocktrace.infrastructure.logging.config import get_logger

MIN_VN_SYMBOL_LENGTH = 2
MAX_VN_SYMBOL_LENGTH = 4


class YahooFinanceNewsProvider:
    """Retrieve latest related news from Yahoo Finance RSS."""

    _feed_url = "https://feeds.finance.yahoo.com/rss/2.0/headline"
    _google_feed_url = "https://news.google.com/rss/search"

    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds
        self._logger = get_logger(__name__)

    async def get_news(self, symbol: str, limit: int) -> list[NewsArticle]:
        """Return latest news articles for a symbol."""
        for candidate in _candidate_symbols(symbol):
            articles = await self._fetch_yahoo_news(candidate, ticker=symbol, limit=limit)
            if articles:
                return articles

        return await self._fetch_google_news(symbol=symbol, limit=limit)

    async def _fetch_yahoo_news(
        self,
        symbol: str,
        ticker: str,
        limit: int,
    ) -> list[NewsArticle]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(
                    self._feed_url,
                    params={"s": symbol, "region": "US", "lang": "en-US"},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            self._logger.warning("yahoo_news_fetch_failed", symbol=symbol, error=str(exc))
            return []

        return _parse_articles(
            response.text,
            ticker=ticker,
            source_fallback="Yahoo Finance",
            limit=limit,
        )

    async def _fetch_google_news(self, symbol: str, limit: int) -> list[NewsArticle]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(
                    self._google_feed_url,
                    params={
                        "q": (
                            f'"{symbol}" '
                            "(cổ phiếu OR chứng khoán OR CafeF OR Vietstock OR "
                            '"Người Quan Sát" OR VietnamBiz OR VnEconomy OR "Báo Đầu Tư")'
                        ),
                        "hl": "vi",
                        "gl": "VN",
                        "ceid": "VN:vi",
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            self._logger.warning("google_news_fetch_failed", symbol=symbol, error=str(exc))
            return []

        return _parse_articles(
            response.text,
            ticker=symbol,
            source_fallback="Google News",
            limit=limit,
        )


def _parse_articles(
    raw_feed: str,
    ticker: str,
    source_fallback: str,
    limit: int,
) -> list[NewsArticle]:
    parsed = feedparser.parse(raw_feed)
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
                ticker=ticker,
                title=title,
                summary=summary,
                url=url,
                source=_source_name(entry.get("source"), fallback=source_fallback),
                published_at=_published_at(entry.get("published_parsed")),
            ),
        )
    return articles


def _published_at(value: object) -> datetime | None:
    if not isinstance(value, struct_time):
        return None
    return datetime(*value[:6], tzinfo=UTC)


def _source_name(value: object, fallback: str) -> str:
    if isinstance(value, dict):
        title = value.get("title")
        if title:
            return str(title)
    if value:
        return str(value)
    return fallback


def _candidate_symbols(symbol: str) -> list[str]:
    normalized = symbol.strip().upper()
    candidates = [normalized]
    if (
        "." not in normalized
        and normalized.isalpha()
        and MIN_VN_SYMBOL_LENGTH <= len(normalized) <= MAX_VN_SYMBOL_LENGTH
    ):
        candidates.append(f"{normalized}.VN")
    return candidates
