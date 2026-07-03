import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, UTC
from decimal import Decimal

from stocktrace.application.services.market_analysis_service import MarketAnalysisService
from stocktrace.application.services.market_data import StockQuote, NewsArticle
from stocktrace.ai.models import MarketAnalysisResult, SentimentLabel


@pytest.fixture
def mock_market_data_service():
    service = AsyncMock()
    service.get_quote.return_value = StockQuote(
        ticker="DUMMY",
        company_name="Dummy",
        current_price=Decimal("10.0"),
        change=Decimal("0.5"),
        change_percent=Decimal("5.0"),
        open_price=Decimal("9.5"),
        high_price=Decimal("10.5"),
        low_price=Decimal("9.0"),
        volume=1000,
        timestamp=datetime.now(UTC),
    )
    service.get_news.return_value = [
        NewsArticle(
            ticker="MARKET",
            title="News 1",
            summary="Summary 1",
            url="http://news1",
            source="Source1",
        )
    ]
    return service


@pytest.fixture
def mock_analysis_service():
    service = AsyncMock()
    service.is_configured = True
    service.analyze_market.return_value = MarketAnalysisResult(
        overview="Overview",
        sentiment=SentimentLabel.POSITIVE,
        positive_sectors="Bank",
        negative_sectors="Real Estate",
        cash_flow="Strong",
        international_impact="Good",
        short_term="Up",
        medium_term="Up",
        risks="None",
        conclusion="Buy",
    )
    return service


@pytest.mark.asyncio
async def test_market_analysis_service_success(mock_market_data_service, mock_analysis_service):
    service = MarketAnalysisService(
        analysis_service=mock_analysis_service,
        market_data_service=mock_market_data_service,
    )

    bundle = await service.analyze_market(news_limit=2)

    assert bundle.indices is not None
    assert bundle.sectors is not None
    assert bundle.international is not None
    assert len(bundle.news) == 1
    assert bundle.analysis is not None
    assert bundle.analysis.sentiment == SentimentLabel.POSITIVE


@pytest.mark.asyncio
async def test_market_analysis_service_ai_disabled(mock_market_data_service, mock_analysis_service):
    mock_analysis_service.is_configured = False
    service = MarketAnalysisService(
        analysis_service=mock_analysis_service,
        market_data_service=mock_market_data_service,
    )

    bundle = await service.analyze_market()

    assert bundle.analysis is None
    mock_analysis_service.analyze_market.assert_not_called()


@pytest.mark.asyncio
async def test_market_analysis_service_partial_data_failure(mock_market_data_service, mock_analysis_service):
    # Simulate quote failure for some indices
    async def side_effect(ticker):
        if ticker == "^VNINDEX":
            raise RuntimeError("Fetch failed")
        return StockQuote(
            ticker=ticker,
            company_name="Mock",
            current_price=Decimal("10.0"),
            change=Decimal("0.5"),
            change_percent=Decimal("5.0"),
            open_price=Decimal("9.5"),
            high_price=Decimal("10.5"),
            low_price=Decimal("9.0"),
            volume=1000,
            timestamp=datetime.now(UTC),
        )

    mock_market_data_service.get_quote.side_effect = side_effect
    
    service = MarketAnalysisService(
        analysis_service=mock_analysis_service,
        market_data_service=mock_market_data_service,
    )

    bundle = await service.analyze_market()

    assert bundle.indices["VNINDEX"] is None
    assert bundle.indices["VN30"] is not None
