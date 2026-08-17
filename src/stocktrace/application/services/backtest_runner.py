"""Replay deterministic suggestion rules over verified historical inputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from stocktrace.domain.entities.investment_suggestion import SuggestionAction
from stocktrace.domain.services.suggestion_audit import SuggestionAuditSnapshot
from stocktrace.domain.services.suggestion_rule_engine import (
    RuleEvaluationInput,
    RuleEvaluationResult,
    SuggestionRuleEngine,
)


@dataclass(frozen=True, slots=True)
class HistoricalSuggestionPoint:
    """One point-in-time, verified input for replaying the live rule engine."""

    point_id: str
    as_of: datetime
    inputs: RuleEvaluationInput

    def __post_init__(self) -> None:
        if not self.point_id.strip():
            raise ValueError("point_id must not be empty.")
        _require_aware_time(self.as_of, "as_of")
        if self.inputs.generated_at > self.as_of:
            raise ValueError("inputs.generated_at must not be later than as_of.")
        if any(item.observed_at > self.as_of for item in self.inputs.evidence):
            raise ValueError("evidence must not be observed after as_of.")
        if any(item.observed_at > self.as_of for item in self.inputs.freshness):
            raise ValueError("freshness must not be observed after as_of.")


@dataclass(frozen=True, slots=True)
class BacktestEvaluation:
    """Rule result and audit snapshot produced from a single historical point."""

    point: HistoricalSuggestionPoint
    result: RuleEvaluationResult
    audit_snapshot: SuggestionAuditSnapshot


@dataclass(frozen=True, slots=True)
class ActionCount:
    """The number of historical evaluations that yielded one rule action."""

    action: SuggestionAction
    count: int


@dataclass(frozen=True, slots=True)
class BacktestReport:
    """Replay report; it intentionally makes no P&L or execution claim."""

    evaluations: tuple[BacktestEvaluation, ...]
    action_counts: tuple[ActionCount, ...]

    @property
    def total_evaluations(self) -> int:
        """Return the number of inputs replayed through the shared rule engine."""
        return len(self.evaluations)

    @property
    def blocked_evaluations(self) -> int:
        """Return evaluations blocked by the same data/rule controls as live."""
        return sum(not item.result.is_actionable for item in self.evaluations)


class BacktestRunner:
    """Replay historical inputs through exactly the same suggestion rule engine."""

    def __init__(self, rule_engine: SuggestionRuleEngine) -> None:
        self._rule_engine = rule_engine

    def run(self, points: tuple[HistoricalSuggestionPoint, ...]) -> BacktestReport:
        """Evaluate ordered historical points without provider, LLM, or broker calls."""
        _ensure_chronological(points)
        evaluations = tuple(
            self._evaluate_point(point)
            for point in points
        )
        counts = {
            action: sum(item.result.action is action for item in evaluations)
            for action in SuggestionAction
        }
        return BacktestReport(
            evaluations=evaluations,
            action_counts=tuple(
                ActionCount(action=action, count=count)
                for action, count in counts.items()
                if count
            ),
        )

    def _evaluate_point(self, point: HistoricalSuggestionPoint) -> BacktestEvaluation:
        result = self._rule_engine.evaluate(point.inputs)
        snapshot = SuggestionAuditSnapshot.from_evaluation(
            point.inputs,
            result,
            snapshot_id=f"backtest:{point.point_id}",
        )
        return BacktestEvaluation(point=point, result=result, audit_snapshot=snapshot)


def _ensure_chronological(points: tuple[HistoricalSuggestionPoint, ...]) -> None:
    latest_by_symbol: dict[str, datetime] = {}
    point_ids: set[str] = set()
    for point in points:
        if point.point_id in point_ids:
            raise ValueError("points must not contain duplicate point_id values.")
        point_ids.add(point.point_id)
        previous = latest_by_symbol.get(point.inputs.symbol)
        if previous is not None and point.as_of <= previous:
            raise ValueError("points for one symbol must be strictly chronological.")
        latest_by_symbol[point.inputs.symbol] = point.as_of


def _require_aware_time(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
