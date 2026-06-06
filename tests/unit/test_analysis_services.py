"""Unit tests for news and liquidity analysis services."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from stocktrace.application.services.liquidity_analysis_service import LiquidityAnalysisService
from stocktrace.application.services.market_data import FundamentalData, HistoricalPrice, NewsArticle, StockQuote
from stocktrace.application.services.news_analysis_service import NewsAnalysisService


def test_news_analysis_detects_positive_sentiment() -> None:
    service = NewsAnalysisService()
    result = service.analyze(
        [
            NewsArticle(
                ticker="VCB",
                title="Vietcombank báo cáo lợi nhuận tăng mạnh",
                summary="Kết quả kinh doanh tích cực",
                url="https://example.com/1",
                source="Test",
            ),
        ],
    )
    assert result.label == "Tích cực"
    assert result.positive_count == 1


def test_news_analysis_detects_negative_sentiment() -> None:
    service = NewsAnalysisService()
    result = service.analyze(
        [
            NewsArticle(
                ticker="VCB",
                title="Lợi nhuận giảm do áp lực chi phí",
                summary="Triển vọng tiêu cực",
                url="https://example.com/2",
                source="Test",
            ),
        ],
    )
    assert result.label == "Tiêu cực"


def test_liquidity_service_detects_high_volume() -> None:
    service = LiquidityAnalysisService()
    history = [
        HistoricalPrice(
            date=datetime(2026, 1, day, tzinfo=UTC),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=1_000_000,
        )
        for day in range(1, 21)
    ]
    quote = StockQuote(
        ticker="VCB",
        company_name="VCB",
        current_price=Decimal("100"),
        change=Decimal("1"),
        change_percent=Decimal("1"),
        open_price=Decimal("99"),
        high_price=Decimal("101"),
        low_price=Decimal("98"),
        volume=2_000_000,
        timestamp=datetime.now(tz=UTC),
        currency="VND",
        source="Test",
    )
    fundamentals = FundamentalData(foreign_buy_vol=100_000, foreign_sell_vol=50_000)

    result = service.analyze(quote, history, fundamentals)

    assert result.status == "Thanh khoản cao"
    assert result.foreign_net_vol == 50_000
    assert result.foreign_flow_label == "Khối ngoại mua ròng"
