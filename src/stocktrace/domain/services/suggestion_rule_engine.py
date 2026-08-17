"""Deterministic rule engine for data-backed investment suggestions.

This module accepts only an explicit deterministic score and verified evidence.
It never calls an LLM, derives a price, sizes an order, or submits one.  Those
concerns remain outside the domain rule boundary and are introduced only in
their later, separately guarded phases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from stocktrace.domain.entities.investment_suggestion import (
    DataFreshness,
    InvalidationCondition,
    InvestmentHorizon,
    InvestmentSuggestion,
    SuggestionAction,
    SuggestionEvidence,
    SuggestionRiskLevel,
)
from stocktrace.domain.services.data_quality_gate import DataQualityAssessment, DataQualityIssue


class RuleInputOrigin(StrEnum):
    """Origins explicitly distinguished at the deterministic decision boundary."""

    DETERMINISTIC = "DETERMINISTIC"
    LLM = "LLM"
    MANUAL = "MANUAL"


class RuleEvaluationIssueCode(StrEnum):
    """Failures that block a rule evaluation independently of data freshness."""

    UNTRUSTED_INPUT_ORIGIN = "UNTRUSTED_INPUT_ORIGIN"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    MISSING_INVALIDATION_CONDITION = "MISSING_INVALIDATION_CONDITION"


@dataclass(frozen=True, slots=True)
class RuleEvaluationIssue:
    """A machine-readable explanation for a non-actionable rule result."""

    code: RuleEvaluationIssueCode
    message: str


@dataclass(frozen=True, slots=True)
class SuggestionRulePolicy:
    """Versioned thresholds for the initial deterministic suggestion strategy."""

    accumulate_minimum_score: Decimal = Decimal("0.70")
    reduce_maximum_score: Decimal = Decimal("0.30")

    def __post_init__(self) -> None:
        _require_probability(self.accumulate_minimum_score, "accumulate_minimum_score")
        _require_probability(self.reduce_maximum_score, "reduce_maximum_score")
        if self.reduce_maximum_score >= self.accumulate_minimum_score:
            raise ValueError("reduce_maximum_score must be less than accumulate_minimum_score.")


@dataclass(frozen=True, slots=True)
class RuleEvaluationInput:
    """Verified inputs for one deterministic suggestion evaluation."""

    symbol: str
    horizon: InvestmentHorizon
    risk_level: SuggestionRiskLevel
    deterministic_score: Decimal
    evidence: tuple[SuggestionEvidence, ...]
    freshness: tuple[DataFreshness, ...]
    invalidation_conditions: tuple[InvalidationCondition, ...]
    quality: DataQualityAssessment
    rule_version: str
    generated_at: datetime
    origin: RuleInputOrigin = RuleInputOrigin.DETERMINISTIC

    def __post_init__(self) -> None:
        _require_probability(self.deterministic_score, "deterministic_score")
        if not self.rule_version.strip():
            raise ValueError("rule_version must not be empty.")
        _require_aware_time(self.generated_at, "generated_at")


@dataclass(frozen=True, slots=True)
class RuleEvaluationResult:
    """A suggestion or a safely non-actionable deterministic decision."""

    action: SuggestionAction
    suggestion: InvestmentSuggestion | None
    quality_issues: tuple[DataQualityIssue, ...] = ()
    rule_issues: tuple[RuleEvaluationIssue, ...] = ()

    def __post_init__(self) -> None:
        has_blockers = bool(self.quality_issues or self.rule_issues)
        if has_blockers:
            if self.action is not SuggestionAction.INSUFFICIENT_EVIDENCE:
                raise ValueError("Blocked evaluations must use INSUFFICIENT_EVIDENCE.")
            if self.suggestion is not None:
                raise ValueError("Blocked evaluations must not create a suggestion.")
            return
        if self.suggestion is None:
            raise ValueError("An unblocked evaluation must include an investment suggestion.")
        if self.action is not self.suggestion.action:
            raise ValueError("result action must match suggestion action.")

    @property
    def is_actionable(self) -> bool:
        """Return whether the rule engine may pass the result to later safeguards."""
        return self.suggestion is not None


@dataclass(frozen=True, slots=True)
class SuggestionRuleEngine:
    """Apply a small, explainable policy after the data-quality gate passes."""

    policy: SuggestionRulePolicy = field(default_factory=SuggestionRulePolicy)

    def evaluate(self, inputs: RuleEvaluationInput) -> RuleEvaluationResult:
        """Create a suggestion or safely return insufficient evidence."""
        if not inputs.quality.is_ready_for_suggestion:
            return RuleEvaluationResult(
                action=SuggestionAction.INSUFFICIENT_EVIDENCE,
                suggestion=None,
                quality_issues=inputs.quality.issues,
            )

        validation_issues = _validate_rule_inputs(inputs)
        if validation_issues:
            return RuleEvaluationResult(
                action=SuggestionAction.INSUFFICIENT_EVIDENCE,
                suggestion=None,
                rule_issues=validation_issues,
            )

        action = self._select_action(inputs.risk_level, inputs.deterministic_score)
        return RuleEvaluationResult(
            action=action,
            suggestion=InvestmentSuggestion(
                symbol=inputs.symbol,
                action=action,
                horizon=inputs.horizon,
                risk_level=inputs.risk_level,
                confidence=inputs.deterministic_score,
                evidence=inputs.evidence,
                freshness=inputs.freshness,
                invalidation_conditions=inputs.invalidation_conditions,
                rule_version=inputs.rule_version,
                generated_at=inputs.generated_at,
            ),
        )

    def _select_action(
        self,
        risk_level: SuggestionRiskLevel,
        deterministic_score: Decimal,
    ) -> SuggestionAction:
        if risk_level is SuggestionRiskLevel.CRITICAL:
            return SuggestionAction.AVOID
        if deterministic_score >= self.policy.accumulate_minimum_score:
            return SuggestionAction.ACCUMULATE_CONDITIONALLY
        if deterministic_score <= self.policy.reduce_maximum_score:
            return SuggestionAction.REDUCE_CONDITIONALLY
        return SuggestionAction.WATCH


def _validate_rule_inputs(inputs: RuleEvaluationInput) -> tuple[RuleEvaluationIssue, ...]:
    issues: list[RuleEvaluationIssue] = []
    if inputs.origin is not RuleInputOrigin.DETERMINISTIC:
        issues.append(
            RuleEvaluationIssue(
                code=RuleEvaluationIssueCode.UNTRUSTED_INPUT_ORIGIN,
                message="LLM hoặc thao tác thủ công không được dùng để quyết định gợi ý đầu tư.",
            ),
        )
    if not inputs.evidence:
        issues.append(
            RuleEvaluationIssue(
                code=RuleEvaluationIssueCode.MISSING_EVIDENCE,
                message="Thiếu bằng chứng đã kiểm chứng cho rule evaluation.",
            ),
        )
    if not inputs.invalidation_conditions:
        issues.append(
            RuleEvaluationIssue(
                code=RuleEvaluationIssueCode.MISSING_INVALIDATION_CONDITION,
                message="Thiếu điều kiện vô hiệu hóa gợi ý.",
            ),
        )
    return tuple(issues)


def _require_probability(value: Decimal, field_name: str) -> None:
    if not Decimal("0") <= value <= Decimal("1"):
        raise ValueError(f"{field_name} must be between 0 and 1.")


def _require_aware_time(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
