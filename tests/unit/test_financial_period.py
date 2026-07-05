"""Unit tests for financial period value object."""

from __future__ import annotations

import pytest

from stocktrace.domain.value_objects.financial_period import FinancialPeriod, PeriodUnit


def test_parse_1y() -> None:
    period = FinancialPeriod.parse("1Y")
    assert period.value == 1
    assert period.unit == PeriodUnit.YEAR
    assert period.label == "1Y"
    assert period.months == 12


def test_parse_6m() -> None:
    period = FinancialPeriod.parse("6M")
    assert period.value == 6
    assert period.unit == PeriodUnit.MONTH
    assert period.months == 6


def test_parse_3y() -> None:
    period = FinancialPeriod.parse("3Y")
    assert period.months == 36


def test_invalid_period_raises() -> None:
    with pytest.raises(ValueError, match="Invalid period"):
        FinancialPeriod.parse("1W")

    with pytest.raises(ValueError, match="positive"):
        FinancialPeriod.parse("0Y")


def test_date_range() -> None:
    period = FinancialPeriod.parse("1Y")
    start, end = period.date_range()
    assert start < end
