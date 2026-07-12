"""Valuation calculation engine."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from stocktrace.domain.entities.financial import (
    FinancialRatio,
    Valuation,
    ValuationStatus,
)


class ValuationEngine:
    """Calculate valuation metrics from ratios and market data."""

    def calculate(
        self,
        symbol: str,
        ratios: list[FinancialRatio],
        current_price: Decimal | None = None,
    ) -> Valuation:
        """Build valuation snapshot from ratio history."""
        if not ratios:
            return Valuation(
                symbol=symbol,
                period_end=date.today(),
                current_pe=None,
                average_pe=None,
                current_pb=None,
                average_pb=None,
                status=ValuationStatus.FAIR,
                current_price=current_price,
            )

        latest = ratios[-1]
        current_pe = latest.pe
        current_pb = latest.pb

        # Historical valuation needs each period's actual market price. Reusing the
        # current price with old EPS/BVPS creates a false P/E or P/B history, so the
        # provider must supply verified historical multiples before this is enabled.
        average_pe = None
        average_pb = None
        status = ValuationStatus.FAIR
        target_price = None
        historical_pe: tuple[tuple[int, Decimal], ...] = ()
        historical_pb: tuple[tuple[int, Decimal], ...] = ()

        return Valuation(
            symbol=symbol,
            period_end=latest.period_end,
            current_pe=current_pe,
            average_pe=average_pe,
            current_pb=current_pb,
            average_pb=average_pb,
            status=status,
            target_price=target_price,
            current_price=current_price,
            historical_pe=historical_pe,
            historical_pb=historical_pb,
        )
