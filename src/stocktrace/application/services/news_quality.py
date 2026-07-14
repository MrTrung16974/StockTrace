"""Freshness and duplicate controls for stock-news responses."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from stocktrace.application.services.market_data import NewsArticle

MAX_NEWS_AGE_DAYS = 7


def select_recent_unique_news(
    articles: list[NewsArticle],
    *,
    limit: int,
    now: datetime | None = None,
) -> list[NewsArticle]:
    """Keep only recent, non-duplicated articles for a stock-news response.

    Articles without a publication timestamp are retained but are explicitly
    identified as unverified by the Telegram formatter.
    """
    reference_time = now or datetime.now(tz=UTC)
    cutoff = reference_time - timedelta(days=MAX_NEWS_AGE_DAYS)
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    selected: list[NewsArticle] = []

    for article in articles:
        published_at = article.published_at
        if published_at is not None:
            published_at = (
                published_at.replace(tzinfo=UTC)
                if published_at.tzinfo is None
                else published_at.astimezone(UTC)
            )
            if published_at < cutoff:
                continue

        url_key = article.url.strip().lower()
        title_key = re.sub(r"\s+", " ", article.title).strip().lower()
        if not url_key or not title_key or url_key in seen_urls or title_key in seen_titles:
            continue

        seen_urls.add(url_key)
        seen_titles.add(title_key)
        selected.append(article)
        if len(selected) >= limit:
            break

    return selected
