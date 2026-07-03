from stocktrace.ai.market_prompt_builder import MarketPromptBuilder
from stocktrace.ai.models import MarketAnalysisContext
from stocktrace.application.services.market_data import StockQuote
from datetime import datetime, UTC
from decimal import Decimal


def test_market_prompt_builder_basic():
    builder = MarketPromptBuilder()
    
    context = MarketAnalysisContext(
        indices={
            "VNINDEX": StockQuote(
                ticker="^VNINDEX",
                company_name="VNINDEX",
                current_price=Decimal("1200"),
                change=Decimal("10"),
                change_percent=Decimal("0.8"),
                open_price=Decimal("1190"),
                high_price=Decimal("1205"),
                low_price=Decimal("1190"),
                volume=1000,
                timestamp=datetime.now(UTC),
            ),
            "UPCOM": None,
        },
        sectors={"Ngân hàng": None},
        international={},
        news=(),
    )
    
    request = builder.build(context)
    
    assert "[TỔNG QUAN]" in request.prompt
    assert "VNINDEX: 1200" in request.prompt
    assert "UPCOM: Không có dữ liệu" in request.prompt
    assert "Không có tin tức mới." in request.prompt
