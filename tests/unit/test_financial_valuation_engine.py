"""Tests for valuation safeguards."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from stocktrace.application.services.financial.valuation_engine import ValuationEngine
from stocktrace.domain.entities.financial import FinancialRatio, ValuationStatus


def test_current_price_is_not_used_to_create_false_historical_multiples() -> None:
    ratios = [
        FinancialRatio(
            symbol="ABC",
            period="FY2024",
            period_end=date(2024, 12, 31),
            pe=Decimal("10"),
            pb=Decimal("1.2"),
        ),
        FinancialRatio(
            symbol="ABC",
            period="FY2025",
            period_end=date(2025, 12, 31),
            pe=Decimal("12"),
            pb=Decimal("1.5"),
        ),
    ]

    valuation = ValuationEngine().calculate("ABC", ratios, current_price=Decimal("30000"))

    assert valuation.current_pe == Decimal("12")
    assert valuation.average_pe is None
    assert valuation.target_price is None
    assert valuation.historical_pe == ()
    assert valuation.status == ValuationStatus.FAIR
