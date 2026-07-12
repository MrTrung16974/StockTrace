"""Financial signal detection engine."""

from __future__ import annotations

from decimal import Decimal

from stocktrace.domain.entities.financial import (
    FinancialRatio,
    FinancialScore,
    FinancialSignal,
    SignalLevel,
    TraceType,
    Valuation,
    ValuationStatus,
)


class FinancialSignalEngine:
    """Detect financial alert signals from analysis data."""

    def detect(
        self,
        ratios: list[FinancialRatio],
        score: FinancialScore,
        valuation: Valuation,
    ) -> tuple[FinancialSignal, ...]:
        """Generate trace signals from financial data."""
        latest = ratios[-1] if ratios else None
        signals: list[FinancialSignal] = []

        signals.append(self._growth_signal(latest))
        signals.append(self._cashflow_signal(latest))
        signals.append(self._profitability_signal(latest))
        signals.append(self._valuation_signal(valuation))
        signals.append(self._risk_signal(latest, score))

        return tuple(signals)

    def _growth_signal(self, latest: FinancialRatio | None) -> FinancialSignal:
        reasons: list[str] = []
        level = SignalLevel.YELLOW

        if latest and latest.revenue_growth is not None:
            if latest.revenue_growth > Decimal("15"):
                reasons.append(f"Doanh thu tăng trên 15% ({latest.revenue_growth:.1f}%)")
                level = SignalLevel.GREEN
            elif latest.revenue_growth > Decimal("0"):
                reasons.append(f"Doanh thu tăng trưởng dương ({latest.revenue_growth:.1f}%)")
            else:
                reasons.append(f"Doanh thu đang giảm ({latest.revenue_growth:.1f}%)")
                level = SignalLevel.RED

        return FinancialSignal(
            trace_type=TraceType.TRACE_GROWTH,
            level=level,
            label="Tín hiệu tăng trưởng tài chính",
            reasons=tuple(reasons),
        )

    def _cashflow_signal(self, latest: FinancialRatio | None) -> FinancialSignal:
        reasons: list[str] = []
        level = SignalLevel.YELLOW

        if latest and latest.operating_cash_flow is not None:
            if latest.operating_cash_flow > 0:
                reasons.append("Dòng tiền từ hoạt động kinh doanh dương")
                level = SignalLevel.GREEN
            else:
                reasons.append("Dòng tiền từ hoạt động kinh doanh âm")
                level = SignalLevel.RED

        if latest and latest.free_cash_flow is not None and latest.free_cash_flow > 0:
            reasons.append("Dòng tiền tự do dương")

        return FinancialSignal(
            trace_type=TraceType.TRACE_CASHFLOW,
            level=level,
            label="Tín hiệu dòng tiền",
            reasons=tuple(reasons),
        )

    def _profitability_signal(self, latest: FinancialRatio | None) -> FinancialSignal:
        reasons: list[str] = []
        level = SignalLevel.YELLOW

        if latest and latest.roe is not None:
            if latest.roe > Decimal("20"):
                reasons.append(f"ROE trên 20% ({latest.roe:.1f}%)")
                level = SignalLevel.GREEN
            elif latest.roe > Decimal("10"):
                reasons.append(f"ROE cao hơn mức trung bình ({latest.roe:.1f}%)")
            else:
                reasons.append(f"ROE thấp hơn mức trung bình ({latest.roe:.1f}%)")
                level = SignalLevel.RED

        return FinancialSignal(
            trace_type=TraceType.TRACE_FINANCIAL,
            level=level,
            label="Tín hiệu khả năng sinh lời",
            reasons=tuple(reasons),
        )

    def _valuation_signal(self, valuation: Valuation) -> FinancialSignal:
        reasons: list[str] = []
        level = SignalLevel.YELLOW

        if valuation.current_pe is not None:
            reasons.append(f"PE hiện tại: {valuation.current_pe:.1f}")
        if valuation.status == ValuationStatus.UNDERVALUED:
            reasons.append("Trạng thái: ĐANG RẺ")
            level = SignalLevel.GREEN
        elif valuation.status == ValuationStatus.OVERVALUED:
            reasons.append("Trạng thái: ĐANG ĐẮT")
            level = SignalLevel.RED
        else:
            reasons.append("Trạng thái: HỢP LÝ")

        return FinancialSignal(
            trace_type=TraceType.TRACE_VALUATION,
            level=level,
            label="Tín hiệu định giá",
            reasons=tuple(reasons),
        )

    def _risk_signal(
        self,
        latest: FinancialRatio | None,
        score: FinancialScore,
    ) -> FinancialSignal:
        reasons: list[str] = []
        level = SignalLevel.YELLOW

        if latest and latest.debt_to_equity is not None:
            if latest.debt_to_equity < Decimal("0.5"):
                reasons.append(f"Tỷ lệ nợ dưới 0,5 ({latest.debt_to_equity:.2f})")
                level = SignalLevel.GREEN
            elif latest.debt_to_equity > Decimal("1.5"):
                reasons.append(f"Tỷ lệ nợ cao ({latest.debt_to_equity:.2f})")
                level = SignalLevel.RED
            else:
                reasons.append(f"Tỷ lệ nợ trung bình ({latest.debt_to_equity:.2f})")

        if score.overall_score >= Decimal("7"):
            reasons.append(f"Điểm tài chính: {score.overall_score}/10")

        return FinancialSignal(
            trace_type=TraceType.TRACE_RISK,
            level=level,
            label="Tín hiệu rủi ro",
            reasons=tuple(reasons),
        )
