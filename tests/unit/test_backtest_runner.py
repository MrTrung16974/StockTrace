"""Tests for Phase-8 replay through the production suggestion rule engine."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from stocktrace.application.services.backtest_runner import (
    BacktestRunner,
    HistoricalSuggestionPoint,
)
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
    SuggestionRuleEngine,
    SuggestionRulePolicy,
)

FIRST = datetime(2026, 1, 2, 9, 0, tzinfo=UTC)
_TWO_EVALUATIONS = 2


def _inputs(
    *,
    score: Decimal,
    as_of: datetime,
    quality: DataQualityAssessment | None = None,
) -> RuleEvaluationInput:
    return RuleEvaluationInput(
        symbol="HPG",
        horizon=InvestmentHorizon.MEDIUM,
        risk_level=SuggestionRiskLevel.MEDIUM,
        deterministic_score=score,
        evidence=(
            SuggestionEvidence(
                "FINANCIAL_SCORE",
                "Điểm tài chính",
                str(score),
                EvidenceDirection.SUPPORTS,
                "vnstock",
                as_of,
            ),
        ),
        freshness=(DataFreshness("quote", "exchange-feed", as_of, timedelta(days=1)),),
        invalidation_conditions=(InvalidationCondition("STALE", "Dữ liệu đã cũ."),),
        quality=quality or DataQualityAssessment(is_ready_for_suggestion=True),
        rule_version="suggestion-rules-v1",
        generated_at=as_of,
    )


def _point(
    point_id: str,
    *,
    score: Decimal,
    as_of: datetime,
    quality: DataQualityAssessment | None = None,
) -> HistoricalSuggestionPoint:
    return HistoricalSuggestionPoint(
        point_id=point_id,
        as_of=as_of,
        inputs=_inputs(score=score, as_of=as_of, quality=quality),
    )


def test_runner_reuses_live_rule_engine_and_creates_auditable_report() -> None:
    runner = BacktestRunner(
        SuggestionRuleEngine(
            SuggestionRulePolicy(
                accumulate_minimum_score=Decimal("0.80"),
                reduce_maximum_score=Decimal("0.20"),
            ),
        ),
    )
    report = runner.run(
        (
            _point("hpg-1", score=Decimal("0.75"), as_of=FIRST),
            _point("hpg-2", score=Decimal("0.90"), as_of=FIRST + timedelta(days=1)),
        ),
    )

    assert [item.result.action for item in report.evaluations] == [
        SuggestionAction.WATCH,
        SuggestionAction.ACCUMULATE_CONDITIONALLY,
    ]
    assert report.total_evaluations == _TWO_EVALUATIONS
    assert report.blocked_evaluations == 0
    assert all(item.audit_snapshot.has_valid_checksum() for item in report.evaluations)
    assert [item.audit_snapshot.snapshot_id for item in report.evaluations] == [
        "backtest:hpg-1",
        "backtest:hpg-2",
    ]


def test_runner_counts_blocked_evaluations_using_the_live_quality_result() -> None:
    quality_issue = DataQualityIssue(
        DataQualityIssueCode.STALE_DATA,
        "quote",
        "Dữ liệu đã cũ.",
    )
    report = BacktestRunner(SuggestionRuleEngine()).run(
        (
            _point(
                "hpg-stale",
                score=Decimal("0.75"),
                as_of=FIRST,
                quality=DataQualityAssessment(False, (quality_issue,)),
            ),
        ),
    )

    assert report.evaluations[0].result.action is SuggestionAction.INSUFFICIENT_EVIDENCE
    assert report.blocked_evaluations == 1
    assert report.evaluations[0].audit_snapshot.quality_issues == (quality_issue,)


def test_historical_point_rejects_future_evidence_or_freshness() -> None:
    future = FIRST + timedelta(minutes=1)
    inputs = _inputs(score=Decimal("0.75"), as_of=FIRST)
    inputs = replace(
        inputs,
        evidence=(replace(inputs.evidence[0], observed_at=future),),
    )

    with pytest.raises(ValueError, match="evidence"):
        HistoricalSuggestionPoint("future-evidence", FIRST, inputs)


def test_runner_rejects_duplicate_ids_and_non_chronological_points() -> None:
    runner = BacktestRunner(SuggestionRuleEngine())
    first = _point("duplicate", score=Decimal("0.75"), as_of=FIRST)
    second = _point("duplicate", score=Decimal("0.75"), as_of=FIRST + timedelta(days=1))

    with pytest.raises(ValueError, match="duplicate"):
        runner.run((first, second))

    later = _point("later", score=Decimal("0.75"), as_of=FIRST + timedelta(days=1))
    earlier = _point("earlier", score=Decimal("0.75"), as_of=FIRST)
    with pytest.raises(ValueError, match="chronological"):
        runner.run((later, earlier))
