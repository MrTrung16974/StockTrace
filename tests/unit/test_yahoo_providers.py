"""Yahoo provider tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
import respx
from httpx import Response

from stocktrace.infrastructure.news.yahoo import YahooFinanceNewsProvider
from stocktrace.infrastructure.providers.yahoo import YahooFinanceQuoteProvider


@pytest.mark.asyncio
@respx.mock
async def test_yahoo_quote_provider_parses_chart_response() -> None:
    respx.get("https://query1.finance.yahoo.com/v8/finance/chart/FPT").mock(
        return_value=Response(
            200,
            json={
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "symbol": "FPT",
                                "regularMarketPrice": 123.45,
                                "chartPreviousClose": 120,
                                "currency": "USD",
                                "regularMarketTime": 1780363800,
                            },
                        },
                    ],
                },
            },
        ),
    )

    provider = YahooFinanceQuoteProvider(timeout_seconds=1)
    quote = await provider.get_quote("FPT")

    assert quote.ticker == "FPT"
    assert quote.current_price == Decimal("123.45")
    assert quote.currency == "USD"
    assert quote.source == "Yahoo Finance"


@pytest.mark.asyncio
@respx.mock
async def test_yahoo_news_provider_parses_rss_response() -> None:
    respx.get("https://feeds.finance.yahoo.com/rss/2.0/headline").mock(
        return_value=Response(
            200,
            text="""<?xml version="1.0"?>
            <rss version="2.0">
              <channel>
                <item>
                  <title>FPT market update</title>
                  <link>https://example.com/fpt</link>
                  <pubDate>Tue, 02 Jun 2026 10:00:00 GMT</pubDate>
                </item>
              </channel>
            </rss>""",
        ),
    )

    provider = YahooFinanceNewsProvider(timeout_seconds=1)
    articles = await provider.get_news("FPT", limit=5)

    assert len(articles) == 1
    assert articles[0].ticker == "FPT"
    assert articles[0].title == "FPT market update"
    assert articles[0].url == "https://example.com/fpt"
