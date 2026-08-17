"""Tamper-evident audit snapshots for deterministic investment suggestions."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from stocktrace.domain.entities.investment_suggestion import (
    DataFreshness,
    SuggestionAction,
    SuggestionEvidence,
)
from stocktrace.domain.services.data_quality_gate import DataQualityIssue
from stocktrace.domain.services.suggestion_rule_engine import (
    RuleEvaluationInput,
    RuleEvaluationIssue,
    RuleEvaluationResult,
)

_SYMBOL_PATTERN = re.compile(r"^[A-Z]{2,10}$")
_CHECKSUM_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class DecisionStepStatus(StrEnum):
    """Outcome of one deterministic decision step captured by the snapshot."""

    PASSED = "PASSED"
    BLOCKED = "BLOCKED"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True, slots=True)
class DecisionTraceStep:
    """A non-sensitive, human-readable stage of a rule evaluation."""

    code: str
    status: DecisionStepStatus
    detail: str

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("code must not be empty.")
        if not self.detail.strip():
            raise ValueError("detail must not be empty.")


@dataclass(frozen=True, slots=True)
class SuggestionAuditSnapshot:
    """Immutable, tamper-evident record of one suggestion rule evaluation.

    It captures only the decision data available through Phase 5.  User approval,
    confirmation, and broker responses are deliberately absent until their own
    later controls and persistence contracts exist.
    """

    snapshot_id: str
    symbol: str
    evaluated_at: datetime
    rule_version: str
    action: SuggestionAction
    suggestion_id: str | None
    evidence: tuple[SuggestionEvidence, ...]
    freshness: tuple[DataFreshness, ...]
    quality_issues: tuple[DataQualityIssue, ...]
    rule_issues: tuple[RuleEvaluationIssue, ...]
    decision_trace: tuple[DecisionTraceStep, ...]
    checksum: str

    def __post_init__(self) -> None:
        if not self.snapshot_id.strip():
            raise ValueError("snapshot_id must not be empty.")
        if not _SYMBOL_PATTERN.fullmatch(self.symbol):
            raise ValueError("symbol must be uppercase alphanumeric and 2-10 characters.")
        _require_aware_time(self.evaluated_at, "evaluated_at")
        if not self.rule_version.strip():
            raise ValueError("rule_version must not be empty.")
        if not self.evidence:
            raise ValueError("evidence must not be empty.")
        if not self.freshness:
            raise ValueError("freshness must not be empty.")
        if not self.decision_trace:
            raise ValueError("decision_trace must not be empty.")
        if not _CHECKSUM_PATTERN.fullmatch(self.checksum):
            raise ValueError("checksum must be a lowercase SHA-256 hex digest.")
        if self.action is SuggestionAction.INSUFFICIENT_EVIDENCE:
            if self.suggestion_id is not None:
                raise ValueError("blocked snapshots must not carry a suggestion_id.")
            return
        if not self.suggestion_id or not self.suggestion_id.strip():
            raise ValueError("actionable snapshots require a suggestion_id.")

    @classmethod
    def from_evaluation(
        cls,
        inputs: RuleEvaluationInput,
        result: RuleEvaluationResult,
        *,
        snapshot_id: str | None = None,
    ) -> SuggestionAuditSnapshot:
        """Create an audit record directly from the phase-4 rule contract."""
        snapshot = cls(
            snapshot_id=snapshot_id or str(uuid4()),
            symbol=inputs.symbol,
            evaluated_at=inputs.generated_at,
            rule_version=inputs.rule_version,
            action=result.action,
            suggestion_id=(
                result.suggestion.suggestion_id if result.suggestion is not None else None
            ),
            evidence=inputs.evidence,
            freshness=inputs.freshness,
            quality_issues=result.quality_issues,
            rule_issues=result.rule_issues,
            decision_trace=_build_decision_trace(inputs, result),
            checksum="0" * 64,
        )
        return cls(
            snapshot_id=snapshot.snapshot_id,
            symbol=snapshot.symbol,
            evaluated_at=snapshot.evaluated_at,
            rule_version=snapshot.rule_version,
            action=snapshot.action,
            suggestion_id=snapshot.suggestion_id,
            evidence=snapshot.evidence,
            freshness=snapshot.freshness,
            quality_issues=snapshot.quality_issues,
            rule_issues=snapshot.rule_issues,
            decision_trace=snapshot.decision_trace,
            checksum=_checksum_for(snapshot),
        )

    def has_valid_checksum(self) -> bool:
        """Return whether the persisted fields still match this snapshot checksum."""
        return self.checksum == _checksum_for(self)


def _build_decision_trace(
    inputs: RuleEvaluationInput,
    result: RuleEvaluationResult,
) -> tuple[DecisionTraceStep, ...]:
    quality_status = (
        DecisionStepStatus.PASSED
        if inputs.quality.is_ready_for_suggestion
        else DecisionStepStatus.BLOCKED
    )
    rule_validation_status = (
        DecisionStepStatus.NOT_EVALUATED
        if result.quality_issues
        else DecisionStepStatus.BLOCKED
        if result.rule_issues
        else DecisionStepStatus.PASSED
    )
    action_status = (
        DecisionStepStatus.BLOCKED
        if result.action is SuggestionAction.INSUFFICIENT_EVIDENCE
        else DecisionStepStatus.PASSED
    )
    return (
        DecisionTraceStep(
            code="DATA_QUALITY_GATE",
            status=quality_status,
            detail="Data quality gate evaluated before deterministic rules.",
        ),
        DecisionTraceStep(
            code="RULE_INPUT_VALIDATION",
            status=rule_validation_status,
            detail=(
                "Only deterministic input with evidence and invalidation conditions "
                "is accepted."
            ),
        ),
        DecisionTraceStep(
            code="SUGGESTION_ACTION",
            status=action_status,
            detail=f"Deterministic result: {result.action.value}.",
        ),
    )


def _checksum_for(snapshot: SuggestionAuditSnapshot) -> str:
    payload = {
        "action": snapshot.action.value,
        "decision_trace": [
            {"code": step.code, "detail": step.detail, "status": step.status.value}
            for step in snapshot.decision_trace
        ],
        "evaluated_at": snapshot.evaluated_at.isoformat(),
        "evidence": [
            {
                "direction": evidence.direction.value,
                "factor_code": evidence.factor_code,
                "label": evidence.label,
                "observed_at": evidence.observed_at.isoformat(),
                "source": evidence.source,
                "source_url": evidence.source_url,
                "value": evidence.value,
            }
            for evidence in snapshot.evidence
        ],
        "freshness": [
            {
                "data_type": freshness.data_type,
                "observed_at": freshness.observed_at.isoformat(),
                "source": freshness.source,
                "ttl_seconds": freshness.ttl.total_seconds(),
            }
            for freshness in snapshot.freshness
        ],
        "quality_issues": [
            {
                "code": issue.code.value,
                "data_type": issue.data_type,
                "message": issue.message,
                "sources": list(issue.sources),
            }
            for issue in snapshot.quality_issues
        ],
        "rule_issues": [
            {"code": issue.code.value, "message": issue.message}
            for issue in snapshot.rule_issues
        ],
        "rule_version": snapshot.rule_version,
        "snapshot_id": snapshot.snapshot_id,
        "suggestion_id": snapshot.suggestion_id,
        "symbol": snapshot.symbol,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _require_aware_time(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
