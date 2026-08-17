"""Tests for Phase-5 tamper-evident suggestion audit snapshots."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from stocktrace.domain.entities.investment_suggestion import (
    DataFreshness,
    EvidenceDirection,
    InvalidationCondition,
    InvestmentHorizon,
    SuggestionAction,
    SuggestionEvidence,
    SuggestionRiskLevel,
)
from stocktrace.domain.services.data_quality_gate import (
    DataQualityAssessment,
    DataQualityIssue,
    DataQualityIssueCode,
)
from stocktrace.domain.services.suggestion_audit import (
    DecisionStepStatus,
    SuggestionAuditSnapshot,
)
from stocktrace.domain.services.suggestion_rule_engine import (
    RuleEvaluationInput,
    SuggestionRuleEngine,
)

NOW = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)


def _inputs(quality: DataQualityAssessment | None = None) -> RuleEvaluationInput:
    return RuleEvaluationInput(
        symbol="HPG",
        horizon=InvestmentHorizon.MEDIUM,
        risk_level=SuggestionRiskLevel.MEDIUM,
        deterministic_score=Decimal("0.75"),
        evidence=(
            SuggestionEvidence(
                factor_code="FINANCIAL_SCORE",
                label="Điểm tài chính",
                value="0.75",
                direction=EvidenceDirection.SUPPORTS,
                source="vnstock",
                observed_at=NOW,
            ),
        ),
        freshness=(
            DataFreshness("quote", "exchange-feed", NOW, timedelta(minutes=5)),
        ),
        invalidation_conditions=(InvalidationCondition("STALE", "Dữ liệu không còn mới."),),
        quality=quality or DataQualityAssessment(is_ready_for_suggestion=True),
        rule_version="suggestion-rules-v1",
        generated_at=NOW,
    )


def test_snapshot_preserves_evaluation_inputs_and_verifies_checksum() -> None:
    inputs = _inputs()
    result = SuggestionRuleEngine().evaluate(inputs)

    snapshot = SuggestionAuditSnapshot.from_evaluation(
        inputs,
        result,
        snapshot_id="snapshot-1",
    )

    assert snapshot.action is SuggestionAction.ACCUMULATE_CONDITIONALLY
    assert snapshot.suggestion_id == result.suggestion.suggestion_id if result.suggestion else None
    assert snapshot.evidence == inputs.evidence
    assert snapshot.freshness == inputs.freshness
    assert snapshot.has_valid_checksum() is True
    assert all(step.status is DecisionStepStatus.PASSED for step in snapshot.decision_trace)


def test_blocked_evaluation_is_audited_without_a_suggestion_id() -> None:
    quality_issue = DataQualityIssue(
        DataQualityIssueCode.STALE_DATA,
        "quote",
        "Dữ liệu quote đã hết hạn.",
        ("exchange-feed",),
    )
    inputs = _inputs(DataQualityAssessment(False, (quality_issue,)))
    result = SuggestionRuleEngine().evaluate(inputs)

    snapshot = SuggestionAuditSnapshot.from_evaluation(
        inputs,
        result,
        snapshot_id="snapshot-2",
    )

    assert snapshot.action is SuggestionAction.INSUFFICIENT_EVIDENCE
    assert snapshot.suggestion_id is None
    assert snapshot.quality_issues == (quality_issue,)
    assert snapshot.has_valid_checksum() is True
    assert snapshot.decision_trace[0].status is DecisionStepStatus.BLOCKED
    assert snapshot.decision_trace[1].status is DecisionStepStatus.NOT_EVALUATED


def test_snapshot_checksum_detects_field_tampering() -> None:
    inputs = _inputs()
    result = SuggestionRuleEngine().evaluate(inputs)
    snapshot = SuggestionAuditSnapshot.from_evaluation(inputs, result, snapshot_id="snapshot-3")

    modified = replace(snapshot, action=SuggestionAction.WATCH)

    assert modified.has_valid_checksum() is False


def test_blocked_snapshot_rejects_suggestion_identifier() -> None:
    inputs = _inputs()
    result = SuggestionRuleEngine().evaluate(inputs)
    snapshot = SuggestionAuditSnapshot.from_evaluation(inputs, result, snapshot_id="snapshot-4")

    with pytest.raises(ValueError, match="blocked snapshots"):
        replace(
            snapshot,
            action=SuggestionAction.INSUFFICIENT_EVIDENCE,
            suggestion_id="suggestion-1",
        )


def test_snapshot_rejects_missing_decision_trace() -> None:
    inputs = _inputs()
    result = SuggestionRuleEngine().evaluate(inputs)
    snapshot = SuggestionAuditSnapshot.from_evaluation(inputs, result, snapshot_id="snapshot-5")

    with pytest.raises(ValueError, match="decision_trace"):
        replace(snapshot, decision_trace=())
