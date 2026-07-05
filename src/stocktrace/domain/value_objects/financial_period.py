"""Financial period value object."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum


class PeriodUnit(StrEnum):
    """Supported financial analysis period units."""

    MONTH = "M"
    YEAR = "Y"


@dataclass(frozen=True, slots=True)
class FinancialPeriod:
    """User-specified analysis period (e.g. 6M, 1Y, 3Y)."""

    value: int
    unit: PeriodUnit

    @classmethod
    def parse(cls, raw: str) -> FinancialPeriod:
        """Parse period string like '6M', '1Y', '3Y'."""
        normalized = raw.strip().upper()
        if not normalized:
            msg = "Period is required (e.g. 6M, 1Y, 3Y)."
            raise ValueError(msg)

        unit_char = normalized[-1]
        if unit_char not in ("M", "Y"):
            msg = f"Invalid period unit '{unit_char}'. Use M (months) or Y (years)."
            raise ValueError(msg)

        try:
            value = int(normalized[:-1])
        except ValueError as exc:
            msg = f"Invalid period value in '{raw}'."
            raise ValueError(msg) from exc

        if value <= 0:
            msg = "Period value must be positive."
            raise ValueError(msg)

        return cls(value=value, unit=PeriodUnit(unit_char))

    @property
    def label(self) -> str:
        """Human-readable period label."""
        if self.unit == PeriodUnit.MONTH:
            return f"{self.value}M"
        return f"{self.value}Y"

    @property
    def months(self) -> int:
        """Total months covered by this period."""
        if self.unit == PeriodUnit.MONTH:
            return self.value
        return self.value * 12

    def date_range(self, end: date | None = None) -> tuple[date, date]:
        """Return (start, end) dates for the period."""
        end_date = end or date.today()
        start_date = end_date - timedelta(days=self.months * 30)
        return start_date, end_date
