"""Yahoo provider tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
import respx
from httpx import Response

from stocktrace.infrastructure.news.yahoo import YahooFinanceNewsProvider
from stocktrace.infrastructure.providers.yahoo import YahooFinanceQuoteProvider

HPG_VOLUME = 20_573_500


@pytest.mark.asyncio
@respx.mock
async def test_yahoo_quote_provider_parses_chart_response() -> None:
    respx.get("https://query1.finance.yahoo.com/v8/finance/chart/FPT.US").mock(
        return_value=Response(
            200,
            json={
                "chart": {
                    "result": [
                            {
                                "meta": {
                                    "symbol": "FPT.US",
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
    quote = await provider.get_quote("FPT.US")

    assert quote.ticker == "FPT.US"
    assert quote.current_price == Decimal("123.45")
    assert quote.currency == "USD"
    assert quote.source == "Yahoo Finance"


@pytest.mark.asyncio
@respx.mock
async def test_yahoo_quote_provider_tries_vietnam_suffix_for_plain_symbol() -> None:
    respx.get("https://query1.finance.yahoo.com/v8/finance/chart/HPG.VN").mock(
        return_value=Response(
            200,
            json={
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "symbol": "HPG.VN",
                                "regularMarketPrice": 28300,
                                "chartPreviousClose": 28000,
                                "currency": "VND",
                                "regularMarketTime": 1780363800,
                            },
                        },
                    ],
                },
            },
        ),
    )

    provider = YahooFinanceQuoteProvider(timeout_seconds=1)
    quote = await provider.get_quote("HPG")

    assert quote.ticker == "HPG.VN"
    assert quote.current_price == Decimal("28300")
    assert quote.change == Decimal("300")
    assert quote.currency == "VND"


@pytest.mark.asyncio
@respx.mock
async def test_yahoo_quote_provider_falls_back_to_vndirect_for_vietnam_symbol() -> None:
    respx.get("https://query1.finance.yahoo.com/v8/finance/chart/HPG.VN").mock(
        return_value=Response(404),
    )
    respx.get("https://query1.finance.yahoo.com/v8/finance/chart/HPG").mock(
        return_value=Response(429),
    )
    respx.get("https://api-finfo.vndirect.com.vn/v4/stock_prices").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "code": "HPG",
                        "date": "2026-06-03",
                        "time": "15:06:05",
                        "open": 23.7,
                        "high": 24.15,
                        "low": 23.6,
                        "close": 24.15,
                        "basicPrice": 23.7,
                        "change": 0.45,
                        "pctChange": 1.8987,
                        "nmVolume": 20573500,
                    },
                ],
            },
        ),
    )
    respx.get("https://api-finfo.vndirect.com.vn/v4/stocks").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "code": "HPG",
                        "shortName": "Hoa Phat",
                        "companyNameEng": "Hoa Phat Group Joint Stock Company",
                    },
                ],
            },
        ),
    )

    provider = YahooFinanceQuoteProvider(timeout_seconds=1)
    quote = await provider.get_quote("HPG")

    assert quote.ticker == "HPG"
    assert quote.company_name == "Hoa Phat Group Joint Stock Company"
    assert quote.current_price == Decimal("24150.0")
    assert quote.change == Decimal("450.00")
    assert quote.change_percent == Decimal("1.8987")
    assert quote.volume == HPG_VOLUME
    assert quote.currency == "VND"
    assert quote.source == "VNDIRECT"


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
    articles = await provider.get_news("FPT.US", limit=5)

    assert len(articles) == 1
    assert articles[0].ticker == "FPT.US"
    assert articles[0].title == "FPT market update"
    assert articles[0].url == "https://example.com/fpt"


@pytest.mark.asyncio
@respx.mock
async def test_vietnam_news_provider_prefers_google_news() -> None:
    yahoo_route = respx.get("https://feeds.finance.yahoo.com/rss/2.0/headline").mock(
        return_value=Response(200, text="<rss><channel /></rss>"),
    )
    google_route = respx.get("https://news.google.com/rss/search").mock(
        return_value=Response(
            200,
            text="""<?xml version="1.0"?>
            <rss version="2.0">
              <channel>
                <item>
                  <title>Cổ phiếu HPG tăng nhờ triển vọng thép</title>
                  <link>https://example.com/hpg</link>
                  <source>Vietstock</source>
                  <pubDate>Tue, 02 Jun 2026 10:00:00 GMT</pubDate>
                </item>
              </channel>
            </rss>""",
        ),
    )

    provider = YahooFinanceNewsProvider(timeout_seconds=1)
    articles = await provider.get_news("HPG", limit=5)

    assert yahoo_route.call_count == 0
    assert google_route.called
    assert len(articles) == 1
    assert articles[0].ticker == "HPG"
    assert articles[0].title == "Cổ phiếu HPG tăng nhờ triển vọng thép"
    assert articles[0].source == "Vietstock"


@pytest.mark.asyncio
@respx.mock
async def test_vietnam_news_provider_filters_unrelated_and_old_google_results() -> None:
    respx.get("https://news.google.com/rss/search").mock(
        return_value=Response(
            200,
            text="""<?xml version="1.0"?>
            <rss version="2.0">
              <channel>
                <item>
                  <title>Kulicke &amp; Soffa: Buy On The TCB Inflection</title>
                  <link>https://seekingalpha.com/article/tcb-inflection</link>
                  <source>seekingalpha.com</source>
                  <pubDate>Tue, 02 Jun 2026 10:00:00 GMT</pubDate>
                </item>
                <item>
                  <title>TCB Stock Price and Chart</title>
                  <link>https://tradingview.com/symbols/HOSE-TCB</link>
                  <source>TradingView</source>
                  <pubDate>Tue, 02 Jun 2018 10:00:00 GMT</pubDate>
                </item>
                <item>
                  <title>Cổ phiếu TCB hút dòng tiền ngân hàng</title>
                  <link>https://vietstock.vn/tcb-ngan-hang.htm</link>
                  <source>Vietstock</source>
                  <pubDate>Tue, 02 Jun 2026 10:00:00 GMT</pubDate>
                </item>
              </channel>
            </rss>""",
        ),
    )

    provider = YahooFinanceNewsProvider(timeout_seconds=1)
    articles = await provider.get_news("TCB", limit=5)

    assert len(articles) == 1
    assert articles[0].title == "Cổ phiếu TCB hút dòng tiền ngân hàng"


@pytest.mark.asyncio
@respx.mock
async def test_vietnam_news_provider_accepts_official_policy_source() -> None:
    respx.get("https://news.google.com/rss/search").mock(
        return_value=Response(
            200,
            text="""<?xml version="1.0"?>
            <rss version="2.0">
              <channel>
                <item>
                  <title>MBB quyet dinh dieu chinh lai suat</title>
                  <link>https://news.google.com/rss/articles/example</link>
                  <source>Ngân hàng Nhà nước Việt Nam</source>
                  <pubDate>Tue, 02 Jun 2026 10:00:00 GMT</pubDate>
                </item>
              </channel>
            </rss>""",
        ),
    )

    provider = YahooFinanceNewsProvider(timeout_seconds=1)
    articles = await provider.get_news("MBB", limit=5)

    assert len(articles) == 1
    assert articles[0].source == "Ngân hàng Nhà nước Việt Nam"


@pytest.mark.asyncio
@respx.mock
async def test_yahoo_news_provider_returns_empty_when_all_sources_fail() -> None:
    respx.get("https://feeds.finance.yahoo.com/rss/2.0/headline").mock(
        side_effect=[Response(404), Response(404)],
    )
    respx.get("https://news.google.com/rss/search").mock(return_value=Response(503))

    provider = YahooFinanceNewsProvider(timeout_seconds=1)
    articles = await provider.get_news("MBB.US", limit=5)

    assert articles == []
