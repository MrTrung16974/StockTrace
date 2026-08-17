"""Deterministic data-quality gate for investment suggestion inputs.

The gate deliberately knows nothing about providers, storage, Telegram, or AI.
It evaluates the already-verified source metadata supplied by an application
use case and makes an explicit allow/block decision for the rule engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from stocktrace.domain.entities.investment_suggestion import DataFreshness, SuggestionAction


class DataQualityIssueCode(StrEnum):
    """Reasons why a rule engine must not produce an actionable suggestion."""

    MISSING_REQUIRED_DATA = "MISSING_REQUIRED_DATA"
    STALE_DATA = "STALE_DATA"
    UNTRUSTED_SOURCE = "UNTRUSTED_SOURCE"
    INSUFFICIENT_SOURCE_DIVERSITY = "INSUFFICIENT_SOURCE_DIVERSITY"


@dataclass(frozen=True, slots=True)
class DataSourceRequirement:
    """Quality policy for one input type required by an investment rule."""

    data_type: str
    trusted_sources: tuple[str, ...]
    minimum_fresh_sources: int = 1

    def __post_init__(self) -> None:
        _require_text(self.data_type, "data_type")
        if not self.trusted_sources:
            raise ValueError("trusted_sources must not be empty.")
        if self.minimum_fresh_sources <= 0:
            raise ValueError("minimum_fresh_sources must be greater than zero.")

        normalized_sources = tuple(source.casefold().strip() for source in self.trusted_sources)
        if any(not source for source in normalized_sources):
            raise ValueError("trusted_sources must not contain empty values.")
        if len(set(normalized_sources)) != len(normalized_sources):
            raise ValueError("trusted_sources must not contain duplicates.")
        if self.minimum_fresh_sources > len(normalized_sources):
            raise ValueError("minimum_fresh_sources cannot exceed trusted_sources.")


@dataclass(frozen=True, slots=True)
class DataQualityIssue:
    """One machine-readable failure that explains a blocked suggestion."""

    code: DataQualityIssueCode
    data_type: str
    message: str
    sources: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DataQualityAssessment:
    """Result consumed by deterministic investment rules and audit logging."""

    is_ready_for_suggestion: bool
    issues: tuple[DataQualityIssue, ...] = ()

    @property
    def required_action(self) -> SuggestionAction | None:
        """Force an insufficient-evidence result whenever the gate blocks."""
        if self.is_ready_for_suggestion:
            return None
        return SuggestionAction.INSUFFICIENT_EVIDENCE


@dataclass(frozen=True, slots=True)
class DataQualityGate:
    """Block deterministic investment rules when required inputs are unreliable."""

    requirements: tuple[DataSourceRequirement, ...]

    def __post_init__(self) -> None:
        if not self.requirements:
            raise ValueError("requirements must not be empty.")
        normalized_types = tuple(
            requirement.data_type.casefold().strip() for requirement in self.requirements
        )
        if len(set(normalized_types)) != len(normalized_types):
            raise ValueError("requirements must not contain duplicate data types.")

    def assess(
        self,
        freshness: tuple[DataFreshness, ...],
        *,
        checked_at: datetime,
    ) -> DataQualityAssessment:
        """Assess input freshness and source policy at one deterministic instant."""
        _require_aware_time(checked_at, "checked_at")
        issues: list[DataQualityIssue] = []

        for requirement in self.requirements:
            data_type_key = requirement.data_type.casefold().strip()
            candidates = tuple(
                item
                for item in freshness
                if item.data_type.casefold().strip() == data_type_key
            )
            if not candidates:
                issues.append(
                    DataQualityIssue(
                        code=DataQualityIssueCode.MISSING_REQUIRED_DATA,
                        data_type=requirement.data_type,
                        message=f"Thiếu dữ liệu bắt buộc: {requirement.data_type}.",
                    ),
                )
                continue

            stale_sources = tuple(
                sorted({item.source for item in candidates if not item.is_fresh_at(checked_at)}),
            )
            if stale_sources:
                issues.append(
                    DataQualityIssue(
                        code=DataQualityIssueCode.STALE_DATA,
                        data_type=requirement.data_type,
                        message=f"Dữ liệu {requirement.data_type} đã hết hạn.",
                        sources=stale_sources,
                    ),
                )

            trusted_sources = {source.casefold().strip() for source in requirement.trusted_sources}
            untrusted_sources = tuple(
                sorted(
                    {
                        item.source
                        for item in candidates
                        if item.source.casefold().strip() not in trusted_sources
                    },
                ),
            )
            if untrusted_sources:
                issues.append(
                    DataQualityIssue(
                        code=DataQualityIssueCode.UNTRUSTED_SOURCE,
                        data_type=requirement.data_type,
                        message=(
                            f"Nguồn dữ liệu {requirement.data_type} "
                            "không thuộc chính sách tin cậy."
                        ),
                        sources=untrusted_sources,
                    ),
                )

            fresh_trusted_sources = {
                item.source.casefold().strip()
                for item in candidates
                if item.is_fresh_at(checked_at)
                and item.source.casefold().strip() in trusted_sources
            }
            if len(fresh_trusted_sources) < requirement.minimum_fresh_sources:
                issues.append(
                    DataQualityIssue(
                        code=DataQualityIssueCode.INSUFFICIENT_SOURCE_DIVERSITY,
                        data_type=requirement.data_type,
                        message=(
                            f"Chưa đủ {requirement.minimum_fresh_sources} nguồn tin cậy, "
                            f"còn hiệu lực cho {requirement.data_type}."
                        ),
                        sources=tuple(sorted(fresh_trusted_sources)),
                    ),
                )

        return DataQualityAssessment(
            is_ready_for_suggestion=not issues,
            issues=tuple(issues),
        )


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty.")


def _require_aware_time(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
