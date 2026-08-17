"""Tests that LLM explanation stays inside an existing suggestion's facts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import SecretStr

from stocktrace.ai.models import LLMRequest, LLMResponse
from stocktrace.ai.suggestion_prompt_builder import SuggestionPromptBuilder
from stocktrace.application.services.suggestion_explanation import (
    SuggestionExplanationService,
    SuggestionExplanationStatus,
)
from stocktrace.domain.entities.investment_suggestion import (
    DataFreshness,
    EvidenceDirection,
    InvalidationCondition,
    InvestmentHorizon,
    InvestmentSuggestion,
    SuggestionAction,
    SuggestionEvidence,
    SuggestionRiskLevel,
)
from stocktrace.infrastructure.config.settings import AISettings

NOW = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
_SAFE_TEMPERATURE = 0.1


class FakeLLM:
    """Deterministic LLM test double."""

    def __init__(self, content: str) -> None:
        self.content = content
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(self.content, "fake", 1.0)


def _suggestion() -> InvestmentSuggestion:
    return InvestmentSuggestion(
        symbol="HPG",
        action=SuggestionAction.ACCUMULATE_CONDITIONALLY,
        horizon=InvestmentHorizon.MEDIUM,
        risk_level=SuggestionRiskLevel.MEDIUM,
        confidence=Decimal("0.75"),
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
        freshness=(DataFreshness("quote", "exchange-feed", NOW, timedelta(minutes=5)),),
        invalidation_conditions=(InvalidationCondition("STALE", "Dữ liệu đã cũ."),),
        rule_version="suggestion-rules-v1",
        generated_at=NOW,
        suggestion_id="suggestion-1",
    )


def _settings(*, enabled: bool = True) -> AISettings:
    return AISettings(enabled=enabled, api_key=SecretStr("test-key"), max_tokens=512)


def test_prompt_uses_only_verified_suggestion_data_and_forbids_ordering() -> None:
    prompt = SuggestionPromptBuilder().build(_suggestion())

    assert "FINANCIAL_SCORE" in prompt.prompt
    assert "suggestion-rules-v1" in prompt.prompt
    assert "khối lượng" in prompt.prompt
    assert "đặt lệnh" in prompt.prompt
    assert prompt.temperature == _SAFE_TEMPERATURE


@pytest.mark.asyncio
async def test_service_returns_guarded_ai_explanation_when_response_follows_contract() -> None:
    llm = FakeLLM(
        "ACCUMULATE_CONDITIONALLY dựa trên FINANCIAL_SCORE. "
        "Cần theo dõi STALE. Thông tin chỉ nhằm mục đích tham khảo.",
    )
    service = SuggestionExplanationService(llm, _settings())

    result = await service.explain(_suggestion())

    assert result.status is SuggestionExplanationStatus.AI_EXPLAINED
    assert result.text == llm.content
    assert len(llm.requests) == 1


@pytest.mark.asyncio
async def test_service_rejects_model_attempt_to_add_a_trade_instruction() -> None:
    llm = FakeLLM(
        "ACCUMULATE_CONDITIONALLY dựa trên FINANCIAL_SCORE và STALE. "
        "Hãy mua ngay 1,000 cổ phiếu.",
    )
    service = SuggestionExplanationService(llm, _settings())

    result = await service.explain(_suggestion())

    assert result.status is SuggestionExplanationStatus.AI_REJECTED
    assert result.text != llm.content
    assert "Action đã được Rule Engine xác định" in result.text
    assert "1,000" not in result.text


@pytest.mark.asyncio
async def test_service_uses_data_only_fallback_when_ai_is_disabled() -> None:
    llm = FakeLLM("unused")
    service = SuggestionExplanationService(llm, _settings(enabled=False))

    result = await service.explain(_suggestion())

    assert result.status is SuggestionExplanationStatus.AI_UNAVAILABLE
    assert llm.requests == []
    assert "FINANCIAL_SCORE" in result.text
