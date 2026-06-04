"""Yahoo Finance RSS news provider."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from time import struct_time
from typing import Any, cast
from urllib.parse import urlparse

import feedparser
import httpx

from stocktrace.application.services.market_data import NewsArticle
from stocktrace.infrastructure.logging.config import get_logger

MIN_VN_SYMBOL_LENGTH = 2
MAX_VN_SYMBOL_LENGTH = 4
MAX_NEWS_AGE_DAYS = 45
VIETNAM_SOURCE_KEYWORDS = {
    "cafef",
    "vietstock",
    "vneconomy",
    "vietnambiz",
    "nguoi quan sat",
    "người quan sát",
    "ndh",
    "stockbiz",
    "vietcap",
    "ssi",
    "vnexpress",
    "tuoi tre",
    "tuổi trẻ",
    "thanh nien",
    "laodong",
    "lao động",
    "theinvestor",
    "baodautu",
    "báo đầu tư",
    "tinnhanhchungkhoan",
    "tin nhanh chứng khoán",
}
MARKET_KEYWORDS = {
    "co phieu",
    "cổ phiếu",
    "chung khoan",
    "chứng khoán",
    "hose",
    "hnx",
    "upcom",
    "vn-index",
    "vnindex",
    "niem yet",
    "niêm yết",
    "giao dich",
    "giao dịch",
}
VN_COMPANY_ALIASES = {
    "FPT": ("fpt",),
    "HPG": ("hoa phat", "hòa phát"),
    "VCB": ("vietcombank", "ngoai thuong", "ngoại thương"),
    "TCB": ("techcombank", "ky thuong", "kỹ thương"),
}


class YahooFinanceNewsProvider:
    """Retrieve latest related news from Yahoo Finance RSS."""

    _feed_url = "https://feeds.finance.yahoo.com/rss/2.0/headline"
    _google_feed_url = "https://news.google.com/rss/search"

    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds
        self._logger = get_logger(__name__)

    async def get_news(self, symbol: str, limit: int) -> list[NewsArticle]:
        """Return latest news articles for a symbol."""
        if _looks_like_vietnam_symbol(symbol):
            articles = await self._fetch_google_news(symbol=symbol, limit=limit)
            if articles:
                return articles

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
                        "q": _google_news_query(symbol),
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
            vietnamese_market_filter=True,
        )


def _parse_articles(
    raw_feed: str,
    ticker: str,
    source_fallback: str,
    limit: int,
    vietnamese_market_filter: bool = False,
) -> list[NewsArticle]:
    parsed = feedparser.parse(raw_feed)
    entries = cast(list[dict[str, Any]], parsed.entries)
    articles: list[NewsArticle] = []
    for entry in entries:
        title = str(entry.get("title") or "").strip()
        url = str(entry.get("link") or "").strip()
        summary = str(entry.get("summary") or entry.get("description") or "").strip() or None
        if not title or not url:
            continue
        published_at = _published_at(entry.get("published_parsed"))
        source = _source_name(entry.get("source"), fallback=source_fallback)
        if vietnamese_market_filter and not _is_relevant_vietnam_market_article(
            ticker=ticker,
            title=title,
            summary=summary,
            source=source,
            url=url,
            published_at=published_at,
        ):
            continue
        articles.append(
            NewsArticle(
                ticker=ticker,
                title=title,
                summary=summary,
                url=url,
                source=source,
                published_at=published_at,
            ),
        )
        if len(articles) >= limit:
            break
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
    if _looks_like_vietnam_symbol(normalized):
        candidates.append(f"{normalized}.VN")
    return candidates


def _looks_like_vietnam_symbol(symbol: str) -> bool:
    normalized = symbol.strip().upper()
    return (
        "." not in normalized
        and normalized.isalpha()
        and MIN_VN_SYMBOL_LENGTH <= len(normalized) <= MAX_VN_SYMBOL_LENGTH
    )


def _google_news_query(symbol: str) -> str:
    normalized = symbol.strip().upper()
    aliases = VN_COMPANY_ALIASES.get(normalized, ())
    symbol_terms = " OR ".join(
        [f'"cổ phiếu {normalized}"', f'"{normalized} stock"', f'"HOSE:{normalized}"'],
    )
    alias_terms = " OR ".join(f'"{alias}"' for alias in aliases)
    company_part = f" OR {alias_terms}" if alias_terms else ""
    return (
        f"({symbol_terms}{company_part}) "
        "(cổ phiếu OR chứng khoán OR HOSE OR VN-Index) "
        "(CafeF OR Vietstock OR VnEconomy OR VietnamBiz OR "
        '"Người Quan Sát" OR "Tin nhanh chứng khoán" OR "Báo Đầu Tư") '
        f"when:{MAX_NEWS_AGE_DAYS}d"
    )


def _is_relevant_vietnam_market_article(
    ticker: str,
    title: str,
    summary: str | None,
    source: str,
    url: str,
    published_at: datetime | None,
) -> bool:
    if published_at is not None:
        article_time = published_at if published_at.tzinfo else published_at.replace(tzinfo=UTC)
        if datetime.now(tz=UTC) - article_time.astimezone(UTC) > timedelta(days=MAX_NEWS_AGE_DAYS):
            return False

    normalized = ticker.strip().upper()
    text = " ".join(part for part in (title, summary or "", source, _url_host(url)) if part).lower()
    aliases = VN_COMPANY_ALIASES.get(normalized, ())
    mentions_company = normalized.lower() in text or any(alias.lower() in text for alias in aliases)
    if not mentions_company:
        return False

    has_market_context = any(keyword in text for keyword in MARKET_KEYWORDS)
    has_vietnam_source = any(keyword in text for keyword in VIETNAM_SOURCE_KEYWORDS)
    return has_market_context or has_vietnam_source


def _url_host(url: str) -> str:
    try:
        return urlparse(url).netloc
    except ValueError:
        return ""
