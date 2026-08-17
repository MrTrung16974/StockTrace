"""Tests for Phase-3 deterministic investment data-quality gate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from stocktrace.domain.entities.investment_suggestion import DataFreshness, SuggestionAction
from stocktrace.domain.services.data_quality_gate import (
    DataQualityGate,
    DataQualityIssueCode,
    DataSourceRequirement,
)

NOW = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)


def _item(
    data_type: str,
    source: str,
    *,
    observed_at: datetime = NOW,
    ttl: timedelta = timedelta(minutes=5),
) -> DataFreshness:
    return DataFreshness(
        data_type=data_type,
        source=source,
        observed_at=observed_at,
        ttl=ttl,
    )


def _gate(*requirements: DataSourceRequirement) -> DataQualityGate:
    return DataQualityGate(requirements=requirements)


def test_gate_accepts_all_required_fresh_trusted_inputs() -> None:
    gate = _gate(
        DataSourceRequirement("quote", ("exchange-feed",)),
        DataSourceRequirement("financials", ("vnstock",)),
    )

    assessment = gate.assess(
        (
            _item("quote", "exchange-feed"),
            _item("financials", "vnstock"),
        ),
        checked_at=NOW,
    )

    assert assessment.is_ready_for_suggestion is True
    assert assessment.issues == ()
    assert assessment.required_action is None


def test_gate_blocks_missing_required_input_with_insufficient_evidence_action() -> None:
    gate = _gate(DataSourceRequirement("quote", ("exchange-feed",)))

    assessment = gate.assess((), checked_at=NOW)

    assert assessment.is_ready_for_suggestion is False
    assert assessment.required_action is SuggestionAction.INSUFFICIENT_EVIDENCE
    assert assessment.issues[0].code is DataQualityIssueCode.MISSING_REQUIRED_DATA


def test_gate_blocks_stale_input_even_when_a_source_is_trusted() -> None:
    gate = _gate(DataSourceRequirement("quote", ("exchange-feed",)))

    assessment = gate.assess(
        (_item("quote", "exchange-feed", observed_at=NOW - timedelta(minutes=6)),),
        checked_at=NOW,
    )

    assert assessment.is_ready_for_suggestion is False
    assert {issue.code for issue in assessment.issues} == {
        DataQualityIssueCode.STALE_DATA,
        DataQualityIssueCode.INSUFFICIENT_SOURCE_DIVERSITY,
    }


def test_gate_blocks_untrusted_source_even_when_it_is_fresh() -> None:
    gate = _gate(DataSourceRequirement("quote", ("exchange-feed",)))

    assessment = gate.assess((_item("quote", "unknown-cache"),), checked_at=NOW)

    assert assessment.is_ready_for_suggestion is False
    assert {issue.code for issue in assessment.issues} == {
        DataQualityIssueCode.UNTRUSTED_SOURCE,
        DataQualityIssueCode.INSUFFICIENT_SOURCE_DIVERSITY,
    }


def test_gate_enforces_distinct_fresh_sources() -> None:
    gate = _gate(
        DataSourceRequirement(
            "news",
            ("google-news", "yahoo-finance"),
            minimum_fresh_sources=2,
        ),
    )

    assessment = gate.assess(
        (
            _item("news", "google-news"),
            _item("news", "google-news"),
        ),
        checked_at=NOW,
    )

    assert assessment.is_ready_for_suggestion is False
    issue = assessment.issues[0]
    assert issue.code is DataQualityIssueCode.INSUFFICIENT_SOURCE_DIVERSITY
    assert issue.sources == ("google-news",)


def test_gate_matches_requirement_type_and_source_without_case_sensitivity() -> None:
    gate = _gate(DataSourceRequirement("Quote", ("Exchange-Feed",)))

    assessment = gate.assess((_item("quote", "exchange-feed"),), checked_at=NOW)

    assert assessment.is_ready_for_suggestion is True


@pytest.mark.parametrize(
    "requirement",
    [
        DataSourceRequirement("quote", ("exchange-feed",)),
    ],
)
def test_gate_requires_timezone_aware_assessment_time(
    requirement: DataSourceRequirement,
) -> None:
    gate = _gate(requirement)

    with pytest.raises(ValueError, match="timezone-aware"):
        gate.assess((_item("quote", "exchange-feed"),), checked_at=datetime(2026, 8, 12, 9, 0))


@pytest.mark.parametrize(
    "trusted_sources,minimum_fresh_sources",
    [
        ((), 1),
        (("exchange-feed", "EXCHANGE-FEED"), 1),
        (("exchange-feed",), 0),
        (("exchange-feed",), 2),
    ],
)
def test_source_requirement_rejects_unsafe_policies(
    trusted_sources: tuple[str, ...],
    minimum_fresh_sources: int,
) -> None:
    with pytest.raises(ValueError):
        DataSourceRequirement(
            "quote",
            trusted_sources,
            minimum_fresh_sources=minimum_fresh_sources,
        )


def test_gate_rejects_duplicate_required_data_types() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        _gate(
            DataSourceRequirement("quote", ("exchange-feed",)),
            DataSourceRequirement("QUOTE", ("secondary-feed",)),
        )
