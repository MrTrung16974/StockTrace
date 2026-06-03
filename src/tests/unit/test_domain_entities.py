"""Unit tests for StockQuote and NewsArticle domain entities."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from stocktrace.domain.entities.news_article import NewsArticle
from stocktrace.domain.entities.stock_quote import StockQuote


def _make_quote(**kwargs) -> StockQuote:
    defaults = dict(
        symbol="FPT",
        price=100.0,
        open=98.0,
        high=102.0,
        low=97.0,
        volume=1_000_000,
        previous_close=99.0,
        currency="VND",
        exchange="HOSE",
        company_name="FPT Corporation",
        fetched_at=datetime.utcnow(),
    )
    defaults.update(kwargs)
    return StockQuote(**defaults)


# ── StockQuote computed properties ────────────────────────────────────────────

class TestStockQuoteChange:
    def test_positive_change(self):
        q = _make_quote(price=105.0, previous_close=100.0)
        assert q.change == pytest.approx(5.0)

    def test_negative_change(self):
        q = _make_quote(price=95.0, previous_close=100.0)
        assert q.change == pytest.approx(-5.0)

    def test_zero_change(self):
        q = _make_quote(price=100.0, previous_close=100.0)
        assert q.change == pytest.approx(0.0)


class TestStockQuoteChangePercent:
    def test_positive_percent(self):
        q = _make_quote(price=110.0, previous_close=100.0)
        assert q.change_percent == pytest.approx(10.0)

    def test_negative_percent(self):
        q = _make_quote(price=90.0, previous_close=100.0)
        assert q.change_percent == pytest.approx(-10.0)

    def test_zero_previous_close_does_not_raise(self):
        q = _make_quote(price=5.0, previous_close=0.0)
        assert q.change_percent == 0.0


class TestStockQuoteChangeEmoji:
    def test_up_emoji_for_gain(self):
        q = _make_quote(price=110.0, previous_close=100.0)
        assert q.change_emoji == "📈"

    def test_down_emoji_for_loss(self):
        q = _make_quote(price=90.0, previous_close=100.0)
        assert q.change_emoji == "📉"

    def test_flat_emoji_for_no_change(self):
        q = _make_quote(price=100.0, previous_close=100.0)
        assert q.change_emoji == "➡️"


class TestStockQuoteImmutability:
    def test_frozen_dataclass_rejects_mutation(self):
        q = _make_quote()
        with pytest.raises((AttributeError, TypeError)):
            q.price = 999.0  # type: ignore[misc]


# ── NewsArticle age_label ─────────────────────────────────────────────────────

class TestNewsArticleAgeLabel:
    def _article(self, published_at: datetime) -> NewsArticle:
        return NewsArticle(
            title="Test", url="https://example.com",
            source="Reuters", symbol="AAPL",
            published_at=published_at,
        )

    def test_minutes_ago(self):
        pub = datetime.utcnow() - timedelta(minutes=30)
        label = self._article(pub).age_label
        assert "phút" in label
        assert "30" in label

    def test_hours_ago(self):
        pub = datetime.utcnow() - timedelta(hours=3)
        label = self._article(pub).age_label
        assert "giờ" in label
        assert "3" in label

    def test_days_ago(self):
        pub = datetime.utcnow() - timedelta(days=2)
        label = self._article(pub).age_label
        assert "ngày" in label
        assert "2" in label

    def test_immutability(self):
        article = self._article(datetime.utcnow())
        with pytest.raises((AttributeError, TypeError)):
            article.title = "mutated"  # type: ignore[misc]
