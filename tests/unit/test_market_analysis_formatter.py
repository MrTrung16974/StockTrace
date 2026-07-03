from stocktrace.infrastructure.telegram.formatters import build_market_analysis_report
from stocktrace.application.services.market_analysis_service import MarketAnalysisBundle
from stocktrace.ai.models import MarketAnalysisResult, SentimentLabel
from stocktrace.application.services.market_data import StockQuote
from datetime import datetime, UTC
from decimal import Decimal


def test_build_market_analysis_report_full():
    bundle = MarketAnalysisBundle(
        timestamp=datetime.now(UTC),
        indices={
            "VNINDEX": StockQuote(
                ticker="^VNINDEX",
                company_name="VNINDEX",
                current_price=Decimal("1200.5"),
                change=Decimal("10.0"),
                change_percent=Decimal("0.85"),
                open_price=Decimal("1190"),
                high_price=Decimal("1205"),
                low_price=Decimal("1190"),
                volume=1000,
                timestamp=datetime.now(UTC),
            )
        },
        sectors={},
        international={},
        news=(),
        analysis=MarketAnalysisResult(
            overview="Thị trường tăng điểm.",
            sentiment=SentimentLabel.POSITIVE,
            positive_sectors="Bank",
            negative_sectors="None",
            cash_flow="Strong",
            international_impact="Neutral",
            short_term="Positive",
            medium_term="Positive",
            risks="Inflation",
            conclusion="Buy",
        )
    )
    
    report = build_market_analysis_report(bundle)
    
    assert "BÁO CÁO THỊ TRƯỜNG TÀI CHÍNH VIỆT NAM" in report
    assert "VNINDEX" in report
    assert "1.200,5" in report or "1_200.5" in report or "1200" in report
    assert "Thị trường tăng điểm." in report
    assert "POSITIVE" in report
    assert "Bank" in report

def test_build_market_analysis_report_no_analysis():
    bundle = MarketAnalysisBundle(
        timestamp=datetime.now(UTC),
        indices={},
        sectors={},
        international={},
        news=(),
        analysis=None,
    )
    
    report = build_market_analysis_report(bundle)
    
    assert "BÁO CÁO THỊ TRƯỜNG TÀI CHÍNH VIỆT NAM" in report
    assert "Không có phân tích AI." in report
