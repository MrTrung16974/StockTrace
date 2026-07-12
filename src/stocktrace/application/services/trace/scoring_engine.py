"""Deterministic trace scoring engine."""

from __future__ import annotations

from decimal import Decimal

from stocktrace.domain.entities.trace import (
    StockTraceEvent,
    TraceScore,
    TraceSeverity,
)

_SEVERITY_WEIGHTS: dict[TraceSeverity, Decimal] = {
    TraceSeverity.INFO: Decimal("0.10"),
    TraceSeverity.LOW: Decimal("0.25"),
    TraceSeverity.MEDIUM: Decimal("0.50"),
    TraceSeverity.HIGH: Decimal("0.80"),
    TraceSeverity.CRITICAL: Decimal("1.00"),
}

_RISK_SEVERITIES = {
    TraceSeverity.MEDIUM,
    TraceSeverity.HIGH,
    TraceSeverity.CRITICAL,
}
_MIN_EVENTS_FOR_CHANGE_SCORE = 2


class TraceScoringEngine:
    """Calculate trace scores from normalized events."""

    def calculate(self, symbol: str, events: tuple[StockTraceEvent, ...]) -> TraceScore:
        """Calculate signal, risk, conviction, and change scores."""
        if not events:
            return TraceScore(
                symbol=symbol,
                signal_score=Decimal("0"),
                risk_score=Decimal("0"),
                conviction_score=Decimal("0"),
                change_score=Decimal("0"),
                event_count=0,
                high_severity_count=0,
            )

        weighted_signal = Decimal("0")
        weighted_risk = Decimal("0")
        confidence_total = Decimal("0")
        high_severity_count = 0

        for event in events:
            severity_weight = _SEVERITY_WEIGHTS[event.severity]
            source_weight = Decimal("1") if event.source.official else Decimal("0.6")
            event_score = severity_weight * event.confidence * source_weight
            weighted_signal += event_score
            confidence_total += event.confidence * source_weight
            if event.severity in _RISK_SEVERITIES:
                weighted_risk += event_score
            if event.severity in (TraceSeverity.HIGH, TraceSeverity.CRITICAL):
                high_severity_count += 1

        count = Decimal(len(events))
        signal_score = self._clamp_100((weighted_signal / count) * Decimal("100"))
        risk_score = self._clamp_100((weighted_risk / count) * Decimal("100"))
        conviction_score = self._clamp_100((confidence_total / count) * Decimal("100"))
        change_score = self._calculate_change_score(events)

        return TraceScore(
            symbol=symbol,
            signal_score=signal_score,
            risk_score=risk_score,
            conviction_score=conviction_score,
            change_score=change_score,
            event_count=len(events),
            high_severity_count=high_severity_count,
        )

    def _calculate_change_score(self, events: tuple[StockTraceEvent, ...]) -> Decimal:
        if len(events) < _MIN_EVENTS_FOR_CHANGE_SCORE:
            return Decimal("0")

        newest = events[: max(1, len(events) // 2)]
        previous = events[max(1, len(events) // 2) :]
        newest_avg = self._average_event_weight(newest)
        previous_avg = self._average_event_weight(previous)
        return self._clamp_100((newest_avg - previous_avg) * Decimal("100"))

    def _average_event_weight(self, events: tuple[StockTraceEvent, ...]) -> Decimal:
        if not events:
            return Decimal("0")
        total = sum((_SEVERITY_WEIGHTS[event.severity] for event in events), Decimal("0"))
        return total / Decimal(len(events))

    def _clamp_100(self, value: Decimal) -> Decimal:
        return max(Decimal("-100"), min(Decimal("100"), value.quantize(Decimal("0.01"))))
