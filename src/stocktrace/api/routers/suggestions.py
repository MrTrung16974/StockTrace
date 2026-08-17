"""Read-only explanation endpoint for existing deterministic suggestions."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from stocktrace.api.dependencies import get_request_container
from stocktrace.api.schemas.suggestions import (
    SuggestionExplainRequest,
    SuggestionExplainResponse,
    SuggestionSummaryResponse,
)
from stocktrace.application.services.suggestion_explanation import SuggestionExplanationService
from stocktrace.bootstrap.container import Container
from stocktrace.domain.entities.investment_suggestion import (
    DataFreshness,
    InvalidationCondition,
    InvestmentSuggestion,
    SuggestionEvidence,
)

router = APIRouter(prefix="/api/v1/suggestions", tags=["suggestions"])


def _explanation_service(container: Container) -> SuggestionExplanationService:
    return container.suggestion_explanation_service()


@router.post("/explain", response_model=SuggestionExplainResponse)
async def explain_suggestion(
    payload: SuggestionExplainRequest,
    container: Annotated[Container, Depends(get_request_container)],
) -> SuggestionExplainResponse:
    """Explain a supplied rule-engine suggestion without creating or confirming an order."""
    try:
        suggestion = InvestmentSuggestion(
            symbol=payload.symbol,
            action=payload.action,
            horizon=payload.horizon,
            risk_level=payload.risk_level,
            confidence=payload.confidence,
            evidence=tuple(
                SuggestionEvidence(
                    factor_code=item.factor_code,
                    label=item.label,
                    value=item.value,
                    direction=item.direction,
                    source=item.source,
                    observed_at=item.observed_at,
                    source_url=item.source_url,
                )
                for item in payload.evidence
            ),
            freshness=tuple(
                DataFreshness(
                    data_type=item.data_type,
                    source=item.source,
                    observed_at=item.observed_at,
                    ttl=timedelta(seconds=item.ttl_seconds),
                )
                for item in payload.freshness
            ),
            invalidation_conditions=tuple(
                InvalidationCondition(code=item.code, description=item.description)
                for item in payload.invalidation_conditions
            ),
            rule_version=payload.rule_version,
            generated_at=payload.generated_at,
            suggestion_id=payload.suggestion_id or str(uuid4()),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    explanation = await _explanation_service(container).explain(suggestion)
    return SuggestionExplainResponse(
        suggestion=SuggestionSummaryResponse(
            suggestion_id=suggestion.suggestion_id,
            symbol=suggestion.symbol,
            action=suggestion.action,
            horizon=suggestion.horizon,
            risk_level=suggestion.risk_level,
            confidence=suggestion.confidence,
            rule_version=suggestion.rule_version,
            generated_at=suggestion.generated_at,
        ),
        explanation=explanation.text,
        ai_status=explanation.status.value,
    )
