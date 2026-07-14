"""Tests for freshness and duplicate controls in stock news."""

from datetime import UTC, datetime, timedelta

from stocktrace.application.services.market_data import NewsArticle
from stocktrace.application.services.news_quality import select_recent_unique_news


def _article(
    title: str,
    url: str,
    published_at: datetime | None,
) -> NewsArticle:
    return NewsArticle(
        ticker="MBB",
        title=title,
        summary=None,
        url=url,
        source="Vietstock",
        published_at=published_at,
    )


def test_news_selection_excludes_old_and_duplicate_articles() -> None:
    now = datetime(2026, 7, 12, 2, 0, tzinfo=UTC)
    selected = select_recent_unique_news(
        [
            _article("MBB profit update", "https://example.com/1", now - timedelta(hours=3)),
            _article(" MBB  profit  update ", "https://example.com/2", now - timedelta(hours=2)),
            _article("MBB old update", "https://example.com/3", now - timedelta(days=8)),
            _article("MBB policy update", "https://example.com/4", now - timedelta(days=1)),
        ],
        limit=5,
        now=now,
    )

    assert [article.url for article in selected] == [
        "https://example.com/1",
        "https://example.com/4",
    ]


def test_news_selection_retains_unknown_publication_time_within_limit() -> None:
    selected = select_recent_unique_news(
        [_article("MBB update", "https://example.com/1", None)],
        limit=5,
        now=datetime(2026, 7, 12, tzinfo=UTC),
    )

    assert len(selected) == 1
