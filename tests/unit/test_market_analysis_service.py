from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from stocktrace.ai.models import MarketAnalysisResult, SentimentLabel
from stocktrace.application.services.market_analysis_service import MarketAnalysisService
from stocktrace.application.services.market_data import (
    NewsArticle,
    ProviderUnavailableError,
    StockQuote,
)


@pytest.fixture
def mock_market_data_service():
    service = AsyncMock()
    service.get_provider_quote.return_value = StockQuote(
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
    service.get_market_news.return_value = [
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


@pytest.fixture
def mock_vietnam_index_provider():
    provider = AsyncMock()
    provider.get_index_quote.return_value = StockQuote(
        ticker="VNINDEX",
        company_name="VNINDEX",
        current_price=Decimal("1300"),
        change=Decimal("5"),
        change_percent=Decimal("0.39"),
        open_price=Decimal("1295"),
        high_price=Decimal("1305"),
        low_price=Decimal("1290"),
        volume=1000,
        timestamp=datetime.now(UTC),
        currency="VND",
        source="vnstock-kbs",
    )
    return provider


@pytest.mark.asyncio
async def test_market_analysis_service_success(
    mock_market_data_service,
    mock_analysis_service,
    mock_vietnam_index_provider,
):
    service = MarketAnalysisService(
        analysis_service=mock_analysis_service,
        market_data_service=mock_market_data_service,
        vietnam_index_provider=mock_vietnam_index_provider,
    )

    bundle = await service.analyze_market(news_limit=2)

    assert bundle.indices is not None
    assert bundle.sectors is not None
    assert bundle.international is not None
    assert len(bundle.news) == 1
    assert bundle.analysis is not None
    assert bundle.analysis.sentiment == SentimentLabel.POSITIVE
    assert bundle.ai_status == "available"
    context = mock_analysis_service.analyze_market.await_args.args[0]
    assert context.news == tuple(bundle.news)
    mock_analysis_service.analyze_market.assert_awaited_once()
    index_calls = mock_vietnam_index_provider.get_index_quote.await_args_list
    index_symbols = [call.args[0] for call in index_calls]
    assert index_symbols == ["VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX"]
    mock_market_data_service.get_quote.assert_not_awaited()


@pytest.mark.asyncio
async def test_market_analysis_service_ai_disabled(mock_market_data_service, mock_analysis_service):
    mock_analysis_service.is_configured = False
    service = MarketAnalysisService(
        analysis_service=mock_analysis_service,
        market_data_service=mock_market_data_service,
    )

    bundle = await service.analyze_market()

    assert bundle.analysis is None
    assert bundle.ai_status == "disabled"
    mock_analysis_service.analyze_market.assert_not_called()


@pytest.mark.asyncio
async def test_market_analysis_keeps_report_when_news_provider_is_unavailable(
    mock_market_data_service,
    mock_analysis_service,
):
    mock_market_data_service.get_market_news.side_effect = ProviderUnavailableError("offline")
    service = MarketAnalysisService(
        analysis_service=mock_analysis_service,
        market_data_service=mock_market_data_service,
    )

    bundle = await service.analyze_market()

    assert bundle.news == ()
    assert bundle.news_error == "Nguồn tin thị trường hiện không phản hồi."
    assert bundle.analysis is not None
    context = mock_analysis_service.analyze_market.await_args.args[0]
    assert context.news == ()


@pytest.mark.asyncio
async def test_market_analysis_service_partial_data_failure(
    mock_market_data_service,
    mock_analysis_service,
    mock_vietnam_index_provider,
):
    # Simulate quote failure for some indices
    async def side_effect(ticker):
        if ticker == "VNINDEX":
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

    mock_vietnam_index_provider.get_index_quote.side_effect = side_effect

    service = MarketAnalysisService(
        analysis_service=mock_analysis_service,
        market_data_service=mock_market_data_service,
        vietnam_index_provider=mock_vietnam_index_provider,
    )

    bundle = await service.analyze_market()

    assert bundle.indices["VNINDEX"] is None
    assert bundle.indices["VN30"] is not None
