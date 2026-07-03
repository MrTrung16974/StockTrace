"""Tests for professional analysis report formatting."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from stocktrace.ai.analysis_service import parse_analysis_response
from stocktrace.ai.models import AnalysisMode
from stocktrace.application.services.liquidity_analysis_service import LiquidityAssessment
from stocktrace.application.services.market_data import FundamentalData, HistoricalPrice, NewsArticle, StockQuote
from stocktrace.application.services.news_analysis_service import NewsSentimentResult
from stocktrace.application.services.stock_analysis_service import AnalysisBundle
from stocktrace.application.services.stock_score_service import StockScore
from stocktrace.application.services.technical_analysis_service import TechnicalIndicators
from stocktrace.infrastructure.telegram.formatters import build_professional_analysis_report


def _sample_quote() -> StockQuote:
    return StockQuote(
        ticker="HPG",
        company_name="Hoa Phat Group",
        current_price=Decimal("23750"),
        change=Decimal("-200"),
        change_percent=Decimal("-0.84"),
        open_price=Decimal("23900"),
        high_price=Decimal("24000"),
        low_price=Decimal("23650"),
        volume=12_500_000,
        timestamp=datetime.now(tz=UTC),
        currency="VND",
        source="VNDIRECT",
    )


def _sample_history() -> tuple[HistoricalPrice, ...]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    points: list[HistoricalPrice] = []
    for index in range(30):
        close = Decimal("23000") + Decimal(index * 25)
        points.append(
            HistoricalPrice(
                date=datetime(2026, 1, 1 + index, tzinfo=UTC) if index < 28 else base.replace(day=1 + index),
                open=close,
                high=close + Decimal("100"),
                low=close - Decimal("100"),
                close=close,
                volume=1_000_000,
            ),
        )
    return tuple(points)


def test_build_professional_analysis_report_uses_required_sections() -> None:
    analysis = parse_analysis_response(
        "HPG",
        "\n".join(
            [
                "[TỔNG QUAN]",
                "HPG đang điều chỉnh nhẹ.",
                "[ĐIỂM TÍCH CỰC]",
                "Thanh khoản tốt",
                "[RỦI RO]",
                "Áp lực bán ngắn hạn",
                "[ĐÁNH GIÁ NGẮN HẠN]",
                "Theo dõi vùng hỗ trợ",
                "[KHUYẾN NGHỊ]",
                "QUAN SÁT | 65% | Thanh khoản ổn | Xu hướng chưa rõ | Chờ tín hiệu",
            ],
        ),
        AnalysisMode.FULL,
    )
    tech = TechnicalIndicators(
        rsi=Decimal("48.5"),
        macd=Decimal("0.12"),
        macd_signal=Decimal("0.08"),
        macd_hist=Decimal("0.04"),
        ema20=Decimal("23600"),
        ema50=Decimal("23400"),
        ema200=Decimal("22800"),
        bb_upper=Decimal("24200"),
        bb_middle=Decimal("23700"),
        bb_lower=Decimal("23200"),
        short_term_trend="Giảm",
        mid_term_trend="Tăng",
        long_term_trend="Tăng",
        support=Decimal("23200"),
        resistance=Decimal("24200"),
        signal="QUAN SÁT",
    )
    message = build_professional_analysis_report(
        AnalysisBundle(
            symbol="HPG",
            quote=_sample_quote(),
            news=(
                NewsArticle(
                    ticker="HPG",
                    title="HPG tăng kỳ vọng lợi nhuận",
                    summary="Tích cực",
                    url="https://example.com/hpg",
                    source="Test",
                ),
            ),
            analysis=analysis,
            technical=tech,
            fundamentals={"PE": "Tốt", "PB": "Trung bình", "ROE": "Tốt", "EPS": "Tốt"},
            fundamental_raw=FundamentalData(
                eps=Decimal("2500"),
                pe=Decimal("12"),
                pb=Decimal("1.8"),
                roe=Decimal("18"),
            ),
            liquidity=LiquidityAssessment(
                avg_volume_20d=10_000_000,
                current_volume=12_500_000,
                volume_ratio=Decimal("1.25"),
                foreign_buy_vol=1_000_000,
                foreign_sell_vol=800_000,
                foreign_net_vol=200_000,
                status="Thanh khoản cao",
                foreign_flow_label="Khối ngoại mua ròng",
            ),
            news_sentiment=NewsSentimentResult(
                label="Tích cực",
                positive_count=1,
                negative_count=0,
                neutral_count=0,
                headline_summary="HPG tăng kỳ vọng lợi nhuận",
            ),
            score=StockScore(
                technical_score=72,
                fundamental_score=78,
                news_score=80,
                momentum_score=75,
                overall_score=76,
                stars="⭐⭐⭐",
            ),
            price_history=_sample_history(),
        ),
    )

    assert "BÁO CÁO PHÂN TÍCH CỔ PHIẾU HPG" in message
    assert "THÔNG TIN DOANH NGHIỆP" in message
    assert "GIÁ HIỆN TẠI" in message
    assert "23.750" in message
    assert "HIỆU SUẤT GIÁ" in message
    assert "PHÂN TÍCH KỸ THUẬT" in message
    assert "PHÂN TÍCH DÒNG TIỀN" in message
    assert "TIN TỨC TÁC ĐỘNG" in message
    assert "PHÂN TÍCH CƠ BẢN" in message
    assert "NHẬN ĐỊNH AI" in message
    assert "76/100" in message
    assert "KỊCH BẢN GIÁ" in message
    assert "KHUYẾN NGHỊ" in message
    assert "⚠️ Đây không phải khuyến nghị đầu tư" in message
