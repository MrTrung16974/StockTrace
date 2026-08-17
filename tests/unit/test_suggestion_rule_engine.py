"""Tests for Phase-4 deterministic suggestion rules."""

from __future__ import annotations

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
from stocktrace.domain.services.suggestion_rule_engine import (
    RuleEvaluationInput,
    RuleEvaluationIssueCode,
    RuleInputOrigin,
    SuggestionRuleEngine,
    SuggestionRulePolicy,
)

NOW = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)


def _input(
    *,
    score: Decimal = Decimal("0.70"),
    risk_level: SuggestionRiskLevel = SuggestionRiskLevel.MEDIUM,
    quality: DataQualityAssessment | None = None,
    origin: RuleInputOrigin = RuleInputOrigin.DETERMINISTIC,
    evidence: tuple[SuggestionEvidence, ...] | None = None,
    invalidation_conditions: tuple[InvalidationCondition, ...] | None = None,
) -> RuleEvaluationInput:
    return RuleEvaluationInput(
        symbol="HPG",
        horizon=InvestmentHorizon.MEDIUM,
        risk_level=risk_level,
        deterministic_score=score,
        evidence=evidence
        if evidence is not None
        else (
            SuggestionEvidence(
                factor_code="FINANCIAL_SCORE",
                label="Điểm tài chính",
                value="0.70",
                direction=EvidenceDirection.SUPPORTS,
                source="vnstock",
                observed_at=NOW,
            ),
        ),
        freshness=(
            DataFreshness("quote", "exchange-feed", NOW, timedelta(minutes=5)),
        ),
        invalidation_conditions=invalidation_conditions
        if invalidation_conditions is not None
        else (InvalidationCondition("STALE", "Dữ liệu không còn mới."),),
        quality=quality or DataQualityAssessment(is_ready_for_suggestion=True),
        rule_version="suggestion-rules-v1",
        generated_at=NOW,
        origin=origin,
    )


@pytest.mark.parametrize(
    ("score", "expected_action"),
    [
        (Decimal("0.70"), SuggestionAction.ACCUMULATE_CONDITIONALLY),
        (Decimal("0.30"), SuggestionAction.REDUCE_CONDITIONALLY),
        (Decimal("0.50"), SuggestionAction.WATCH),
    ],
)
def test_engine_selects_action_from_deterministic_score(
    score: Decimal,
    expected_action: SuggestionAction,
) -> None:
    result = SuggestionRuleEngine().evaluate(_input(score=score))

    assert result.action is expected_action
    assert result.is_actionable is True
    assert result.suggestion is not None
    assert result.suggestion.confidence == score


def test_critical_risk_overrides_a_positive_score_with_avoid() -> None:
    result = SuggestionRuleEngine().evaluate(
        _input(score=Decimal("0.95"), risk_level=SuggestionRiskLevel.CRITICAL),
    )

    assert result.action is SuggestionAction.AVOID
    assert result.suggestion is not None


def test_quality_failure_prevents_suggestion_creation() -> None:
    quality_issue = DataQualityIssue(
        code=DataQualityIssueCode.STALE_DATA,
        data_type="quote",
        message="Dữ liệu quote đã hết hạn.",
    )
    result = SuggestionRuleEngine().evaluate(
        _input(quality=DataQualityAssessment(False, (quality_issue,))),
    )

    assert result.action is SuggestionAction.INSUFFICIENT_EVIDENCE
    assert result.is_actionable is False
    assert result.suggestion is None
    assert result.quality_issues == (quality_issue,)


@pytest.mark.parametrize(
    ("origin", "evidence", "invalidation_conditions", "expected_issue"),
    [
        (RuleInputOrigin.LLM, None, None, RuleEvaluationIssueCode.UNTRUSTED_INPUT_ORIGIN),
        (RuleInputOrigin.DETERMINISTIC, (), None, RuleEvaluationIssueCode.MISSING_EVIDENCE),
        (
            RuleInputOrigin.DETERMINISTIC,
            None,
            (),
            RuleEvaluationIssueCode.MISSING_INVALIDATION_CONDITION,
        ),
    ],
)
def test_invalid_rule_inputs_return_insufficient_evidence(
    origin: RuleInputOrigin,
    evidence: tuple[SuggestionEvidence, ...] | None,
    invalidation_conditions: tuple[InvalidationCondition, ...] | None,
    expected_issue: RuleEvaluationIssueCode,
) -> None:
    result = SuggestionRuleEngine().evaluate(
        _input(
            origin=origin,
            evidence=evidence,
            invalidation_conditions=invalidation_conditions,
        ),
    )

    assert result.action is SuggestionAction.INSUFFICIENT_EVIDENCE
    assert result.suggestion is None
    assert expected_issue in {issue.code for issue in result.rule_issues}


@pytest.mark.parametrize(
    "thresholds",
    [
        (Decimal("0.30"), Decimal("0.30")),
        (Decimal("1.01"), Decimal("0.20")),
        (Decimal("0.70"), Decimal("-0.01")),
    ],
)
def test_policy_rejects_invalid_thresholds(thresholds: tuple[Decimal, Decimal]) -> None:
    with pytest.raises(ValueError):
        SuggestionRulePolicy(*thresholds)
