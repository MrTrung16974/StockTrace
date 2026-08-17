"""Request and response models for presentation-only investment suggestions."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from stocktrace.domain.entities.investment_suggestion import (
    EvidenceDirection,
    InvestmentHorizon,
    SuggestionAction,
    SuggestionRiskLevel,
)


class SuggestionEvidenceRequest(BaseModel):
    """One verified evidence item to explain."""

    factor_code: str
    label: str
    value: str
    direction: EvidenceDirection
    source: str
    observed_at: datetime
    source_url: str | None = None


class DataFreshnessRequest(BaseModel):
    """Freshness metadata for a verified suggestion input."""

    data_type: str
    source: str
    observed_at: datetime
    ttl_seconds: int = Field(gt=0)


class InvalidationConditionRequest(BaseModel):
    """A condition that invalidates the already-created suggestion."""

    code: str
    description: str


class SuggestionExplainRequest(BaseModel):
    """A verified rule-engine suggestion; this endpoint never creates one."""

    symbol: str
    action: SuggestionAction
    horizon: InvestmentHorizon
    risk_level: SuggestionRiskLevel
    confidence: Decimal = Field(ge=0, le=1)
    evidence: list[SuggestionEvidenceRequest] = Field(min_length=1)
    freshness: list[DataFreshnessRequest] = Field(min_length=1)
    invalidation_conditions: list[InvalidationConditionRequest] = Field(min_length=1)
    rule_version: str
    generated_at: datetime
    suggestion_id: str | None = None


class SuggestionSummaryResponse(BaseModel):
    """The immutable deterministic decision shown to the caller."""

    suggestion_id: str
    symbol: str
    action: SuggestionAction
    horizon: InvestmentHorizon
    risk_level: SuggestionRiskLevel
    confidence: Decimal
    rule_version: str
    generated_at: datetime


class SuggestionExplainResponse(BaseModel):
    """Presentation output; it intentionally contains no order fields."""

    suggestion: SuggestionSummaryResponse
    explanation: str
    ai_status: str
