"""Integration tests for Yahoo Finance and News providers (HTTP mocked)."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
import respx
from httpx import Response

from stocktrace.infrastructure.providers.yahoo_finance_provider import YahooFinanceProvider
from stocktrace.infrastructure.providers.yahoo_news_provider import YahooNewsProvider


# ── Yahoo Finance Provider ────────────────────────────────────────────────────

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/AAPL"
SUMMARY_URL_PREFIX = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/AAPL"

CHART_RESPONSE = {
    "chart": {
        "result": [
            {
                "meta": {
                    "symbol": "AAPL",
                    "longName": "Apple Inc.",
                    "regularMarketPrice": 189.50,
                    "regularMarketOpen": 188.00,
                    "regularMarketDayHigh": 191.00,
                    "regularMarketDayLow": 187.50,
                    "regularMarketVolume": 55_000_000,
                    "chartPreviousClose": 187.00,
                    "currency": "USD",
                    "exchangeName": "NASDAQ",
                }
            }
        ]
    }
}

SUMMARY_RESPONSE = {
    "quoteSummary": {
        "result": [
            {
                "price": {
                    "marketCap": {"raw": 2_900_000_000_000, "fmt": "2.9T"},
                },
                "summaryDetail": {
                    "trailingPE": {"raw": 31.5, "fmt": "31.50"},
                    "fiftyTwoWeekHigh": {"raw": 199.62, "fmt": "199.62"},
                    "fiftyTwoWeekLow": {"raw": 124.17, "fmt": "124.17"},
                },
                "defaultKeyStatistics": {},
            }
        ]
    }
}


@pytest.mark.asyncio
@respx.mock
async def test_yahoo_finance_provider_parses_basic_quote():
    respx.get(CHART_URL).mock(return_value=Response(200, json=CHART_RESPONSE))
    respx.get(url__startswith=SUMMARY_URL_PREFIX).mock(
        return_value=Response(200, json=SUMMARY_RESPONSE)
    )

    provider = YahooFinanceProvider(timeout=5)
    quote = await provider.get_quote("AAPL")

    assert quote is not None
    assert quote.symbol == "AAPL"
    assert quote.price == pytest.approx(189.50)
    assert quote.open == pytest.approx(188.00)
    assert quote.high == pytest.approx(191.00)
    assert quote.low == pytest.approx(187.50)
    assert quote.volume == 55_000_000
    assert quote.previous_close == pytest.approx(187.00)
    assert quote.currency == "USD"
    assert quote.exchange == "NASDAQ"
    assert quote.company_name == "Apple Inc."


@pytest.mark.asyncio
@respx.mock
async def test_yahoo_finance_provider_merges_extended_data():
    respx.get(CHART_URL).mock(return_value=Response(200, json=CHART_RESPONSE))
    respx.get(url__startswith=SUMMARY_URL_PREFIX).mock(
        return_value=Response(200, json=SUMMARY_RESPONSE)
    )

    provider = YahooFinanceProvider(timeout=5)
    quote = await provider.get_quote("AAPL")

    assert quote is not None
    assert quote.market_cap == pytest.approx(2_900_000_000_000)
    assert quote.pe_ratio == pytest.approx(31.5)
    assert quote.week_52_high == pytest.approx(199.62)
    assert quote.week_52_low == pytest.approx(124.17)


@pytest.mark.asyncio
@respx.mock
async def test_yahoo_finance_provider_returns_none_on_empty_result():
    respx.get(CHART_URL).mock(
        return_value=Response(200, json={"chart": {"result": []}})
    )
    respx.get(url__startswith=SUMMARY_URL_PREFIX).mock(
        return_value=Response(200, json={"quoteSummary": {"result": []}})
    )

    provider = YahooFinanceProvider(timeout=5)
    quote = await provider.get_quote("AAPL")

    assert quote is None


@pytest.mark.asyncio
@respx.mock
async def test_yahoo_finance_provider_returns_none_on_http_error():
    respx.get(CHART_URL).mock(return_value=Response(404))

    provider = YahooFinanceProvider(timeout=5)
    quote = await provider.get_quote("AAPL")

    assert quote is None


@pytest.mark.asyncio
@respx.mock
async def test_yahoo_finance_provider_falls_back_when_summary_fails():
    """Extended data failure should not prevent returning the base quote."""
    respx.get(CHART_URL).mock(return_value=Response(200, json=CHART_RESPONSE))
    respx.get(url__startswith=SUMMARY_URL_PREFIX).mock(return_value=Response(500))

    provider = YahooFinanceProvider(timeout=5)
    quote = await provider.get_quote("AAPL")

    # Base quote still returned, extended fields absent
    assert quote is not None
    assert quote.price == pytest.approx(189.50)
    assert quote.market_cap is None
    assert quote.week_52_high is None


# ── Yahoo News Provider ───────────────────────────────────────────────────────

YAHOO_RSS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline"
GOOGLE_RSS_URL_PREFIX = "https://news.google.com/rss/search"

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Yahoo Finance</title>
    <item>
      <title>Apple reports record Q2 revenue</title>
      <link>https://finance.yahoo.com/news/apple-q2-revenue</link>
      <source>Reuters</source>
      <pubDate>Tue, 03 Jun 2026 09:30:00 GMT</pubDate>
    </item>
    <item>
      <title>AAPL stock hits new high</title>
      <link>https://finance.yahoo.com/news/aapl-new-high</link>
      <source>Bloomberg</source>
      <pubDate>Tue, 03 Jun 2026 08:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


@pytest.mark.asyncio
@respx.mock
async def test_yahoo_news_provider_parses_rss_articles():
    respx.get(YAHOO_RSS_URL).mock(return_value=Response(200, text=SAMPLE_RSS))

    provider = YahooNewsProvider(timeout=5)
    articles = await provider.get_news("AAPL", limit=5)

    assert len(articles) == 2
    assert articles[0].title == "Apple reports record Q2 revenue"
    assert articles[0].url == "https://finance.yahoo.com/news/apple-q2-revenue"
    assert articles[0].source == "Reuters"
    assert articles[0].symbol == "AAPL"


@pytest.mark.asyncio
@respx.mock
async def test_yahoo_news_provider_respects_limit():
    respx.get(YAHOO_RSS_URL).mock(return_value=Response(200, text=SAMPLE_RSS))

    provider = YahooNewsProvider(timeout=5)
    articles = await provider.get_news("AAPL", limit=1)

    assert len(articles) == 1
    assert articles[0].title == "Apple reports record Q2 revenue"


@pytest.mark.asyncio
@respx.mock
async def test_yahoo_news_provider_falls_back_to_google_news():
    """When Yahoo RSS returns nothing, fall back to Google News RSS."""
    empty_rss = """<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>"""
    google_rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Google: AAPL update</title>
      <link>https://news.google.com/articles/aapl-update</link>
      <pubDate>Tue, 03 Jun 2026 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

    respx.get(YAHOO_RSS_URL).mock(return_value=Response(200, text=empty_rss))
    respx.get(url__startswith=GOOGLE_RSS_URL_PREFIX).mock(
        return_value=Response(200, text=google_rss)
    )

    provider = YahooNewsProvider(timeout=5)
    articles = await provider.get_news("AAPL", limit=5)

    assert len(articles) == 1
    assert articles[0].title == "Google: AAPL update"


@pytest.mark.asyncio
@respx.mock
async def test_yahoo_news_provider_returns_empty_on_both_failures():
    respx.get(YAHOO_RSS_URL).mock(return_value=Response(500))
    respx.get(url__startswith=GOOGLE_RSS_URL_PREFIX).mock(return_value=Response(500))

    provider = YahooNewsProvider(timeout=5)
    articles = await provider.get_news("AAPL", limit=5)

    assert articles == []
