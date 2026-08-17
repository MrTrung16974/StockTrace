"""Detect presentation-only alerts when verified suggestions change or expire."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from stocktrace.domain.entities.investment_suggestion import InvestmentSuggestion


class SuggestionAlertKind(StrEnum):
    """Changes that are meaningful enough to notify without creating an order."""

    ACTION_CHANGED = "ACTION_CHANGED"
    RISK_LEVEL_CHANGED = "RISK_LEVEL_CHANGED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True, slots=True)
class SuggestionAlert:
    """One immutable notification-worthy change in a verified suggestion."""

    kind: SuggestionAlertKind
    symbol: str
    current: InvestmentSuggestion
    previous: InvestmentSuggestion | None = None


class SuggestionAlertService:
    """Compare periodic verified suggestions without making trading decisions."""

    def __init__(self) -> None:
        self._last_by_symbol: dict[str, InvestmentSuggestion] = {}
        self._last_invalid_by_symbol: dict[str, bool] = {}

    def detect(
        self,
        current_suggestions: tuple[InvestmentSuggestion, ...],
        *,
        checked_at: datetime,
    ) -> tuple[SuggestionAlert, ...]:
        """Return newly changed or newly invalidated suggestions.

        The first observation is baseline only. Missing symbols are intentionally
        not treated as invalidation because an upstream provider outage must not
        become an invented market conclusion.
        """
        _require_aware_time(checked_at)
        current_by_symbol = {item.symbol: item for item in current_suggestions}
        if len(current_by_symbol) != len(current_suggestions):
            raise ValueError("current_suggestions must not contain duplicate symbols.")

        alerts: list[SuggestionAlert] = []
        for symbol, current in current_by_symbol.items():
            previous = self._last_by_symbol.get(symbol)
            current_invalid = _is_invalidated(current, checked_at)
            if previous is not None:
                previous_invalid = self._last_invalid_by_symbol.get(symbol, False)
                if current_invalid and not previous_invalid:
                    alerts.append(
                        SuggestionAlert(
                            kind=SuggestionAlertKind.INVALIDATED,
                            symbol=symbol,
                            current=current,
                            previous=previous,
                        ),
                    )
                elif not current_invalid:
                    if current.action is not previous.action:
                        alerts.append(
                            SuggestionAlert(
                                kind=SuggestionAlertKind.ACTION_CHANGED,
                                symbol=symbol,
                                current=current,
                                previous=previous,
                            ),
                        )
                    if current.risk_level is not previous.risk_level:
                        alerts.append(
                            SuggestionAlert(
                                kind=SuggestionAlertKind.RISK_LEVEL_CHANGED,
                                symbol=symbol,
                                current=current,
                                previous=previous,
                            ),
                        )
            self._last_by_symbol[symbol] = current
            self._last_invalid_by_symbol[symbol] = current_invalid
        return tuple(alerts)


def _is_invalidated(suggestion: InvestmentSuggestion, checked_at: datetime) -> bool:
    return any(not freshness.is_fresh_at(checked_at) for freshness in suggestion.freshness)


def _require_aware_time(checked_at: datetime) -> None:
    if checked_at.tzinfo is None or checked_at.utcoffset() is None:
        raise ValueError("checked_at must be timezone-aware.")
