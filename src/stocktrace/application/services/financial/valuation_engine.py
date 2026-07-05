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
        pe_values = [r.pe for r in ratios if r.pe is not None]
        pb_values = [r.pb for r in ratios if r.pb is not None]

        current_pe = latest.pe
        average_pe = (
            sum(pe_values, Decimal("0")) / Decimal(str(len(pe_values))) if pe_values else None
        )
        current_pb = latest.pb
        average_pb = (
            sum(pb_values, Decimal("0")) / Decimal(str(len(pb_values))) if pb_values else None
        )

        status = self._determine_status(current_pe, average_pe)
        target_price = self._estimate_target(current_price, current_pe, average_pe)

        historical_pe = tuple(
            (r.period_end.year, r.pe) for r in ratios if r.pe is not None
        )
        historical_pb = tuple(
            (r.period_end.year, r.pb) for r in ratios if r.pb is not None
        )

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

    def _determine_status(
        self,
        current_pe: Decimal | None,
        average_pe: Decimal | None,
    ) -> ValuationStatus:
        if current_pe is None or average_pe is None:
            return ValuationStatus.FAIR
        if current_pe < average_pe * Decimal("0.85"):
            return ValuationStatus.UNDERVALUED
        if current_pe > average_pe * Decimal("1.15"):
            return ValuationStatus.OVERVALUED
        return ValuationStatus.FAIR

    def _estimate_target(
        self,
        current_price: Decimal | None,
        current_pe: Decimal | None,
        average_pe: Decimal | None,
    ) -> Decimal | None:
        if current_price is None or current_pe is None or average_pe is None:
            return None
        if current_pe == 0:
            return None
        eps_implied = current_price / current_pe
        return (eps_implied * average_pe).quantize(Decimal("1"))
