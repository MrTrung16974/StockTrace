from __future__ import annotations

import logging
from datetime import datetime
from typing import List
from xml.etree import ElementTree

import httpx

from stocktrace.domain.entities.news_article import NewsArticle
from stocktrace.domain.ports.providers import NewsProvider

logger = logging.getLogger(__name__)

# Yahoo Finance RSS feed — no auth required
_YAHOO_RSS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
# Google News RSS as fallback for broader coverage
_GOOGLE_NEWS_URL = "https://news.google.com/rss/search?q={symbol}+stock&hl=en-US&gl=US&ceid=US:en"


class YahooNewsProvider(NewsProvider):
    """
    Outbound adapter: fetches news via Yahoo Finance and Google News RSS feeds.

    No API key required. Falls back to Google News if Yahoo returns nothing.
    """

    def __init__(self, timeout: int = 10) -> None:
        self._timeout = timeout

    async def get_news(self, symbol: str, limit: int = 5) -> List[NewsArticle]:
        articles = await self._fetch_yahoo_rss(symbol, limit)
        if not articles:
            logger.info("YahooNews: no Yahoo RSS results for %s, trying Google News", symbol)
            articles = await self._fetch_google_rss(symbol, limit)
        return articles[:limit]

    async def _fetch_yahoo_rss(self, symbol: str, limit: int) -> List[NewsArticle]:
        url = _YAHOO_RSS_URL.format(symbol=symbol)
        return await self._parse_rss(url, symbol, limit)

    async def _fetch_google_rss(self, symbol: str, limit: int) -> List[NewsArticle]:
        url = _GOOGLE_NEWS_URL.format(symbol=symbol)
        return await self._parse_rss(url, symbol, limit)

    async def _parse_rss(self, url: str, symbol: str, limit: int) -> List[NewsArticle]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()

            root = ElementTree.fromstring(resp.text)
            ns = {"media": "http://search.yahoo.com/mrss/"}
            items = root.findall(".//item")
            articles: List[NewsArticle] = []

            for item in items[:limit]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                source = (item.findtext("source") or item.findtext("author") or "Yahoo Finance").strip()
                pub_date_str = item.findtext("pubDate") or ""
                thumbnail = None

                # Try media:thumbnail
                thumb_el = item.find("media:thumbnail", ns)
                if thumb_el is not None:
                    thumbnail = thumb_el.get("url")

                try:
                    from email.utils import parsedate_to_datetime
                    published_at = parsedate_to_datetime(pub_date_str).replace(tzinfo=None)
                except Exception:
                    published_at = datetime.utcnow()

                if title and link:
                    articles.append(
                        NewsArticle(
                            title=title,
                            url=link,
                            source=source,
                            symbol=symbol,
                            published_at=published_at,
                            thumbnail=thumbnail,
                        )
                    )
            return articles
        except Exception as exc:
            logger.error("RSS parse error for %s from %s: %s", symbol, url, exc)
            return []

    async def is_healthy(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(_YAHOO_RSS_URL.format(symbol="AAPL"))
                return resp.status_code == 200
        except Exception:
            return False
