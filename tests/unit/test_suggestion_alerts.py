"""Tests for Phase-7 suggestion change and invalidation alerts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from stocktrace.application.services.suggestion_alerts import (
    SuggestionAlertKind,
    SuggestionAlertService,
)
from stocktrace.domain.entities.investment_suggestion import (
    DataFreshness,
    EvidenceDirection,
    InvalidationCondition,
    InvestmentHorizon,
    InvestmentSuggestion,
    SuggestionAction,
    SuggestionEvidence,
    SuggestionRiskLevel,
)

NOW = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)


def _suggestion(
    *,
    action: SuggestionAction = SuggestionAction.WATCH,
    risk: SuggestionRiskLevel = SuggestionRiskLevel.MEDIUM,
    observed_at: datetime = NOW,
) -> InvestmentSuggestion:
    return InvestmentSuggestion(
        symbol="HPG",
        action=action,
        horizon=InvestmentHorizon.MEDIUM,
        risk_level=risk,
        confidence=Decimal("0.60"),
        evidence=(
            SuggestionEvidence(
                "FINANCIAL_SCORE",
                "Điểm tài chính",
                "0.60",
                EvidenceDirection.SUPPORTS,
                "vnstock",
                NOW,
            ),
        ),
        freshness=(DataFreshness("quote", "exchange-feed", observed_at, timedelta(minutes=5)),),
        invalidation_conditions=(InvalidationCondition("STALE", "Dữ liệu đã cũ."),),
        rule_version="suggestion-rules-v1",
        generated_at=NOW,
    )


def test_first_observation_sets_a_baseline_without_alerting() -> None:
    service = SuggestionAlertService()

    alerts = service.detect((_suggestion(),), checked_at=NOW)

    assert alerts == ()


def test_service_alerts_when_action_and_risk_change() -> None:
    service = SuggestionAlertService()
    service.detect((_suggestion(),), checked_at=NOW)

    alerts = service.detect(
        (
            _suggestion(
                action=SuggestionAction.ACCUMULATE_CONDITIONALLY,
                risk=SuggestionRiskLevel.HIGH,
            ),
        ),
        checked_at=NOW,
    )

    assert {alert.kind for alert in alerts} == {
        SuggestionAlertKind.ACTION_CHANGED,
        SuggestionAlertKind.RISK_LEVEL_CHANGED,
    }


def test_service_alerts_once_when_suggestion_becomes_stale() -> None:
    service = SuggestionAlertService()
    service.detect((_suggestion(),), checked_at=NOW)
    expired_at = NOW + timedelta(minutes=6)

    first = service.detect((_suggestion(),), checked_at=expired_at)
    repeated = service.detect((_suggestion(),), checked_at=expired_at + timedelta(minutes=1))

    assert [alert.kind for alert in first] == [SuggestionAlertKind.INVALIDATED]
    assert repeated == ()


def test_missing_symbol_is_not_an_invalidation_alert() -> None:
    service = SuggestionAlertService()
    service.detect((_suggestion(),), checked_at=NOW)

    alerts = service.detect((), checked_at=NOW + timedelta(minutes=6))

    assert alerts == ()


def test_service_rejects_duplicate_symbols_and_naive_time() -> None:
    service = SuggestionAlertService()

    with pytest.raises(ValueError, match="duplicate"):
        service.detect((_suggestion(), _suggestion()), checked_at=NOW)
    with pytest.raises(ValueError, match="timezone-aware"):
        service.detect((_suggestion(),), checked_at=datetime(2026, 8, 12, 9, 0))
