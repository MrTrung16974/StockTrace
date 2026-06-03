"""Stock API endpoint tests."""

from __future__ import annotations

import pytest
import respx
from httpx import Response


@respx.mock
def test_get_quote_endpoint_returns_latest_quote(client) -> None:
    respx.get("https://query1.finance.yahoo.com/v8/finance/chart/FPT").mock(
        return_value=Response(
            200,
            json={
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "symbol": "FPT",
                                "longName": "FPT Corporation",
                                "regularMarketPrice": 125000,
                                "chartPreviousClose": 123500,
                                "regularMarketOpen": 124000,
                                "regularMarketDayHigh": 126000,
                                "regularMarketDayLow": 122000,
                                "regularMarketVolume": 2350000,
                                "currency": "VND",
                                "regularMarketTime": 1780492200,
                            },
                        },
                    ],
                },
            },
        ),
    )

    response = client.get("/api/v1/stocks/FPT/quote")

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "FPT"
    assert body["company_name"] == "FPT Corporation"
    assert body["current_price"] == 125000.0
    assert body["change"] == 1500.0
    assert body["change_percent"] == pytest.approx(1.2146, rel=1e-4)
    assert body["volume"] == 2350000


@respx.mock
def test_get_news_endpoint_returns_articles(client) -> None:
    respx.get("https://feeds.finance.yahoo.com/rss/2.0/headline").mock(
        return_value=Response(
            200,
            text="""<?xml version="1.0"?>
            <rss version="2.0">
              <channel>
                <item>
                  <title>FPT closes higher</title>
                  <description>FPT shares moved higher in afternoon trade.</description>
                  <link>https://example.com/fpt-1</link>
                  <pubDate>Tue, 03 Jun 2026 10:00:00 GMT</pubDate>
                </item>
              </channel>
            </rss>""",
        ),
    )

    response = client.get("/api/v1/stocks/FPT/news")

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "FPT"
    assert len(body["articles"]) == 1
    assert body["articles"][0]["title"] == "FPT closes higher"
    assert body["articles"][0]["summary"] == "FPT shares moved higher in afternoon trade."
    assert body["articles"][0]["url"] == "https://example.com/fpt-1"
