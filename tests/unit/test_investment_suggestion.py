"""Tests for Phase-2 suggestion and draft trade-intent contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from stocktrace.domain.entities.investment_suggestion import (
    DataFreshness,
    EvidenceDirection,
    InvalidationCondition,
    InvestmentHorizon,
    InvestmentSuggestion,
    SuggestionAction,
    SuggestionEvidence,
    SuggestionRiskLevel,
    TradeIntentDraft,
    TradeSide,
)

NOW = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)


def _evidence() -> SuggestionEvidence:
    return SuggestionEvidence(
        factor_code="FINANCIAL_SCORE",
        label="Điểm tài chính",
        value="8.1/10",
        direction=EvidenceDirection.SUPPORTS,
        source="vnstock",
        observed_at=NOW,
        source_url="https://example.com/source",
    )


def _freshness() -> DataFreshness:
    return DataFreshness(
        data_type="quote",
        source="official-provider",
        observed_at=NOW,
        ttl=timedelta(minutes=5),
    )


def _suggestion(
    action: SuggestionAction = SuggestionAction.ACCUMULATE_CONDITIONALLY,
) -> InvestmentSuggestion:
    return InvestmentSuggestion(
        symbol="HPG",
        action=action,
        horizon=InvestmentHorizon.MEDIUM,
        risk_level=SuggestionRiskLevel.MEDIUM,
        confidence=Decimal("0.75"),
        evidence=(_evidence(),),
        freshness=(_freshness(),),
        invalidation_conditions=(
            InvalidationCondition("PRICE_BREAKDOWN", "Giá đóng cửa dưới ngưỡng hỗ trợ."),
        ),
        rule_version="suggestion-rules-v1",
        generated_at=NOW,
    )


def test_investment_suggestion_requires_verified_contract_fields() -> None:
    suggestion = _suggestion()

    assert suggestion.symbol == "HPG"
    assert suggestion.action is SuggestionAction.ACCUMULATE_CONDITIONALLY
    assert suggestion.evidence[0].direction is EvidenceDirection.SUPPORTS
    assert "không phải khuyến nghị đầu tư" in suggestion.disclaimer


def test_data_freshness_detects_expired_data() -> None:
    freshness = _freshness()

    assert freshness.is_fresh_at(NOW + timedelta(minutes=5)) is True
    assert freshness.is_fresh_at(NOW + timedelta(minutes=5, seconds=1)) is False


@pytest.mark.parametrize(
    ("symbol", "confidence"),
    [("hpg", Decimal("0.5")), ("HPG", Decimal("1.01"))],
)
def test_investment_suggestion_rejects_invalid_symbol_or_confidence(
    symbol: str,
    confidence: Decimal,
) -> None:
    with pytest.raises(ValueError):
        InvestmentSuggestion(
            symbol=symbol,
            action=SuggestionAction.WATCH,
            horizon=InvestmentHorizon.SHORT,
            risk_level=SuggestionRiskLevel.HIGH,
            confidence=confidence,
            evidence=(_evidence(),),
            freshness=(_freshness(),),
            invalidation_conditions=(InvalidationCondition("STALE", "Dữ liệu quá cũ."),),
            rule_version="suggestion-rules-v1",
            generated_at=NOW,
        )


def test_investment_suggestion_requires_evidence_freshness_and_invalidation() -> None:
    with pytest.raises(ValueError, match="evidence"):
        InvestmentSuggestion(
            symbol="HPG",
            action=SuggestionAction.INSUFFICIENT_EVIDENCE,
            horizon=InvestmentHorizon.SHORT,
            risk_level=SuggestionRiskLevel.HIGH,
            confidence=Decimal("0"),
            evidence=(),
            freshness=(_freshness(),),
            invalidation_conditions=(InvalidationCondition("MISSING", "Thiếu dữ liệu."),),
            rule_version="suggestion-rules-v1",
            generated_at=NOW,
        )


def test_trade_intent_draft_accepts_deterministic_conditional_buy() -> None:
    suggestion = _suggestion()
    intent = TradeIntentDraft(
        owner_id="user-1",
        account_reference="paper-account-1",
        suggestion_id=suggestion.suggestion_id,
        symbol=suggestion.symbol,
        suggestion_action=suggestion.action,
        side=TradeSide.BUY,
        quantity=100,
        limit_price=Decimal("25000"),
        created_at=NOW,
    )

    assert intent.side is TradeSide.BUY
    assert intent.state.value == "DRAFT"


@pytest.mark.parametrize(
    ("action", "side"),
    [
        (SuggestionAction.ACCUMULATE_CONDITIONALLY, TradeSide.SELL),
        (SuggestionAction.REDUCE_CONDITIONALLY, TradeSide.BUY),
        (SuggestionAction.WATCH, TradeSide.BUY),
    ],
)
def test_trade_intent_draft_rejects_action_side_combinations(
    action: SuggestionAction,
    side: TradeSide,
) -> None:
    with pytest.raises(ValueError):
        TradeIntentDraft(
            owner_id="user-1",
            account_reference="paper-account-1",
            suggestion_id="suggestion-1",
            symbol="HPG",
            suggestion_action=action,
            side=side,
            quantity=100,
            limit_price=Decimal("25000"),
            created_at=NOW,
        )


def test_contracts_reject_naive_timestamps_and_invalid_ttl() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        SuggestionEvidence(
            factor_code="QUOTE",
            label="Giá",
            value="25000",
            direction=EvidenceDirection.NEUTRAL,
            source="provider",
            observed_at=datetime(2026, 8, 12, 9, 0),
        )
    with pytest.raises(ValueError, match="ttl"):
        DataFreshness(
            data_type="quote",
            source="provider",
            observed_at=NOW,
            ttl=timedelta(0),
        )
