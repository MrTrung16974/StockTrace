"""Unit tests for Telegram message builder functions."""

from __future__ import annotations

from datetime import datetime

from stocktrace.domain.entities.news_article import NewsArticle
from stocktrace.domain.entities.stock_quote import StockQuote
from stocktrace.infrastructure.telegram.message_builder import (
    build_news_message,
    build_no_price_message,
    build_no_symbol_message,
    build_price_message,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_quote(**kwargs) -> StockQuote:
    defaults = dict(
        symbol="AAPL",
        price=189.50,
        open=188.00,
        high=191.00,
        low=187.50,
        volume=55_000_000,
        previous_close=187.00,
        currency="USD",
        exchange="NASDAQ",
        company_name="Apple Inc.",
        fetched_at=datetime(2026, 6, 3, 10, 0, 0),
    )
    defaults.update(kwargs)
    return StockQuote(**defaults)


def _make_article(**kwargs) -> NewsArticle:
    defaults = dict(
        title="Apple Q2 earnings beat estimates",
        url="https://example.com/news/aapl",
        source="Reuters",
        symbol="AAPL",
        published_at=datetime(2026, 6, 3, 9, 30, 0),
    )
    defaults.update(kwargs)
    return NewsArticle(**defaults)


# ── build_price_message ───────────────────────────────────────────────────────

class TestBuildPriceMessage:
    def test_contains_symbol_and_company(self):
        msg = build_price_message(_make_quote())
        assert "AAPL" in msg
        assert "Apple Inc." in msg

    def test_shows_current_price_with_currency(self):
        msg = build_price_message(_make_quote(price=189.50, currency="USD"))
        assert "189.50" in msg
        assert "USD" in msg

    def test_positive_change_has_plus_sign(self):
        # price=189.50 vs previous_close=187.00 → change = +2.50
        msg = build_price_message(_make_quote(price=189.50, previous_close=187.00))
        assert "+" in msg

    def test_negative_change_has_minus_sign(self):
        msg = build_price_message(_make_quote(price=180.00, previous_close=187.00))
        assert "-" in msg

    def test_shows_ohlc_fields(self):
        msg = build_price_message(_make_quote(
            open=188.00, high=191.00, low=187.50, previous_close=187.00
        ))
        assert "188.00" in msg  # open
        assert "191.00" in msg  # high
        assert "187.50" in msg  # low

    def test_shows_volume(self):
        msg = build_price_message(_make_quote(volume=55_000_000))
        assert "55,000,000" in msg

    def test_shows_exchange(self):
        msg = build_price_message(_make_quote(exchange="NASDAQ"))
        assert "NASDAQ" in msg

    def test_52_week_range_shown_when_present(self):
        msg = build_price_message(_make_quote(week_52_high=199.00, week_52_low=124.00))
        assert "199.00" in msg
        assert "124.00" in msg

    def test_52_week_range_omitted_when_none(self):
        msg = build_price_message(_make_quote(week_52_high=None, week_52_low=None))
        assert "52" not in msg

    def test_market_cap_shown_in_billions(self):
        msg = build_price_message(_make_quote(market_cap=2.9e12))
        assert "2.90T" in msg

    def test_market_cap_shown_in_millions(self):
        msg = build_price_message(_make_quote(market_cap=500e6))
        assert "500.00M" in msg

    def test_market_cap_omitted_when_none(self):
        msg = build_price_message(_make_quote(market_cap=None))
        assert "Vốn hóa" not in msg

    def test_fetched_at_timestamp_present(self):
        msg = build_price_message(_make_quote(fetched_at=datetime(2026, 6, 3, 10, 0, 0)))
        assert "10:00:00" in msg

    def test_uses_html_bold_tag(self):
        msg = build_price_message(_make_quote())
        assert "<b>" in msg

    def test_emoji_up_for_positive_change(self):
        msg = build_price_message(_make_quote(price=190.00, previous_close=187.00))
        assert "📈" in msg

    def test_emoji_down_for_negative_change(self):
        msg = build_price_message(_make_quote(price=180.00, previous_close=187.00))
        assert "📉" in msg

    def test_emoji_flat_for_no_change(self):
        msg = build_price_message(_make_quote(price=187.00, previous_close=187.00))
        assert "➡️" in msg


# ── build_news_message ────────────────────────────────────────────────────────

class TestBuildNewsMessage:
    def test_contains_symbol_in_header(self):
        msg = build_news_message("AAPL", [_make_article()])
        assert "AAPL" in msg

    def test_lists_article_titles_as_links(self):
        article = _make_article(
            title="Apple Q2 earnings beat estimates",
            url="https://example.com/news/aapl",
        )
        msg = build_news_message("AAPL", [article])
        assert "Apple Q2 earnings beat estimates" in msg
        assert "https://example.com/news/aapl" in msg

    def test_uses_html_anchor_tags(self):
        msg = build_news_message("AAPL", [_make_article()])
        assert "<a href=" in msg

    def test_shows_source(self):
        msg = build_news_message("AAPL", [_make_article(source="Reuters")])
        assert "Reuters" in msg

    def test_shows_age_label(self):
        """age_label is generated by NewsArticle; just ensure it appears."""
        msg = build_news_message("AAPL", [_make_article()])
        # Should contain time indicator (phút/giờ/ngày trước)
        assert "trước" in msg

    def test_handles_multiple_articles(self):
        articles = [
            _make_article(title=f"Article {i}", url=f"https://example.com/{i}")
            for i in range(1, 4)
        ]
        msg = build_news_message("AAPL", articles)
        assert "Article 1" in msg
        assert "Article 2" in msg
        assert "Article 3" in msg

    def test_empty_articles_returns_not_found_message(self):
        msg = build_news_message("AAPL", [])
        assert "AAPL" in msg
        assert "không tìm thấy" in msg.lower() or "Không" in msg

    def test_articles_numbered(self):
        articles = [_make_article(title=f"News {i}") for i in range(1, 3)]
        msg = build_news_message("AAPL", articles)
        assert "1." in msg
        assert "2." in msg


# ── build_no_price_message ────────────────────────────────────────────────────

class TestBuildNoPriceMessage:
    def test_contains_symbol(self):
        msg = build_no_price_message("XYZ")
        assert "XYZ" in msg

    def test_suggests_vn_suffix(self):
        msg = build_no_price_message("HPG")
        assert ".VN" in msg

    def test_shows_example_command(self):
        msg = build_no_price_message("HPG")
        assert "/price" in msg


# ── build_no_symbol_message ───────────────────────────────────────────────────

class TestBuildNoSymbolMessage:
    def test_price_command_hint(self):
        msg = build_no_symbol_message("price")
        assert "/price" in msg
        assert "SYMBOL" in msg or "symbol" in msg.lower() or "AAPL" in msg

    def test_news_command_hint(self):
        msg = build_no_symbol_message("news")
        assert "/news" in msg
