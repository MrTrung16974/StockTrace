"""Unit tests for technical analysis calculations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from stocktrace.application.services.market_data import HistoricalPrice
from stocktrace.application.services.technical_analysis_service import TechnicalAnalysisService


def _build_uptrend_history(length: int = 260) -> list[HistoricalPrice]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    prices: list[HistoricalPrice] = []
    for index in range(length):
        close = Decimal(str(100 + index * 0.5))
        prices.append(
            HistoricalPrice(
                date=start + timedelta(days=index),
                open=close - Decimal("1"),
                high=close + Decimal("1"),
                low=close - Decimal("2"),
                close=close,
                volume=1_000_000 + index * 1000,
            ),
        )
    return prices


def test_rsi_is_within_bounds_for_uptrend() -> None:
    service = TechnicalAnalysisService()
    indicators = service.analyze(_build_uptrend_history())

    assert indicators.rsi is not None
    assert Decimal("0") <= indicators.rsi <= Decimal("100")


def test_ema200_requires_sufficient_history() -> None:
    service = TechnicalAnalysisService()
    short = service.analyze(_build_uptrend_history(length=50))
    long = service.analyze(_build_uptrend_history(length=260))

    assert short.ema200 is None
    assert long.ema200 is not None
    assert long.ema20 is not None
    assert long.ema50 is not None
    assert long.ema20 > long.ema200


def test_macd_histogram_positive_in_uptrend() -> None:
    service = TechnicalAnalysisService()
    indicators = service.analyze(_build_uptrend_history(length=260))

    assert indicators.macd is not None
    assert indicators.macd_signal is not None
    assert indicators.macd_hist is not None
    assert indicators.macd_hist >= 0


def test_bollinger_bands_ordering() -> None:
    service = TechnicalAnalysisService()
    indicators = service.analyze(_build_uptrend_history(length=60))

    assert indicators.bb_upper is not None
    assert indicators.bb_middle is not None
    assert indicators.bb_lower is not None
    assert indicators.bb_upper > indicators.bb_middle > indicators.bb_lower


def test_support_resistance_and_signal() -> None:
    service = TechnicalAnalysisService()
    indicators = service.analyze(_build_uptrend_history(length=60))

    assert indicators.support is not None
    assert indicators.resistance is not None
    assert indicators.resistance >= indicators.support
    assert indicators.signal in {"MUA", "BÁN", "GIỮ", "QUAN SÁT"}
