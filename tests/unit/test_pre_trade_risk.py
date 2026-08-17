"""Tests for Phase-12 deterministic pre-trade risk controls."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from stocktrace.domain.entities.investment_suggestion import (
    SuggestionAction,
    TradeIntentDraft,
    TradeSide,
)
from stocktrace.domain.entities.paper_trading import (
    PaperAccountSnapshot,
    PaperExecutionStatus,
    PaperPosition,
    PaperTradeApproval,
)
from stocktrace.domain.entities.pre_trade_risk import RiskControlCode, RiskPolicy
from stocktrace.domain.services.pre_trade_risk import PreTradeRiskEngine
from stocktrace.infrastructure.paper_trading.paper_broker import PaperBroker

NOW = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)


def _policy() -> RiskPolicy:
    return RiskPolicy(
        max_quantity_per_order=100,
        max_notional_per_order=Decimal("3000000"),
        max_orders_per_day=2,
        policy_version="risk-policy-v1",
    )


def _intent(
    *,
    side: TradeSide = TradeSide.BUY,
    quantity: int = 100,
    limit_price: Decimal = Decimal("25000"),
) -> TradeIntentDraft:
    return TradeIntentDraft(
        owner_id="owner-1",
        account_reference="paper-1",
        suggestion_id="suggestion-1",
        symbol="HPG",
        suggestion_action=(
            SuggestionAction.ACCUMULATE_CONDITIONALLY
            if side is TradeSide.BUY
            else SuggestionAction.REDUCE_CONDITIONALLY
        ),
        side=side,
        quantity=quantity,
        limit_price=limit_price,
        created_at=NOW,
        intent_id="intent-1",
    )


def _account(
    *,
    cash: Decimal = Decimal("3000000"),
    positions: tuple[PaperPosition, ...] = (),
    owner_id: str = "owner-1",
) -> PaperAccountSnapshot:
    return PaperAccountSnapshot("paper-1", owner_id, cash, positions)


def _codes(
    *,
    intent: TradeIntentDraft,
    account: PaperAccountSnapshot | None,
    orders: int = 0,
) -> set[RiskControlCode]:
    decision = PreTradeRiskEngine().assess(
        intent,
        account,
        orders_submitted_today=orders,
        policy=_policy(),
        checked_at=NOW,
    )
    return {item.code for item in decision.violations}


def test_risk_engine_approves_order_inside_every_limit() -> None:
    decision = PreTradeRiskEngine().assess(
        _intent(),
        _account(),
        orders_submitted_today=1,
        policy=_policy(),
        checked_at=NOW,
    )

    assert decision.is_approved is True
    assert decision.violations == ()
    assert decision.policy_version == "risk-policy-v1"


@pytest.mark.parametrize(
    ("intent", "account", "orders", "expected"),
    [
        (
            _intent(quantity=101),
            _account(cash=Decimal("3000000")),
            0,
            RiskControlCode.MAX_QUANTITY_EXCEEDED,
        ),
        (
            _intent(limit_price=Decimal("30001")),
            _account(cash=Decimal("4000000")),
            0,
            RiskControlCode.MAX_NOTIONAL_EXCEEDED,
        ),
        (
            _intent(),
            _account(),
            2,
            RiskControlCode.DAILY_ORDER_LIMIT_EXCEEDED,
        ),
        (
            _intent(),
            _account(cash=Decimal("1")),
            0,
            RiskControlCode.INSUFFICIENT_CASH,
        ),
        (
            _intent(side=TradeSide.SELL),
            _account(),
            0,
            RiskControlCode.INSUFFICIENT_POSITION,
        ),
        (_intent(), None, 0, RiskControlCode.ACCOUNT_UNAVAILABLE),
        (
            _intent(),
            _account(owner_id="other-owner"),
            0,
            RiskControlCode.ACCOUNT_OWNER_MISMATCH,
        ),
    ],
)
def test_risk_engine_blocks_each_required_control(
    intent: TradeIntentDraft,
    account: PaperAccountSnapshot | None,
    orders: int,
    expected: RiskControlCode,
) -> None:
    codes = _codes(intent=intent, account=account, orders=orders)

    assert expected in codes


def test_risk_engine_uses_current_position_for_sell() -> None:
    decision = PreTradeRiskEngine().assess(
        _intent(side=TradeSide.SELL),
        _account(positions=(PaperPosition("HPG", 100),)),
        orders_submitted_today=0,
        policy=_policy(),
        checked_at=NOW,
    )

    assert decision.is_approved is True


def test_risk_engine_rejects_invalid_count_or_time() -> None:
    with pytest.raises(ValueError, match="negative"):
        PreTradeRiskEngine().assess(
            _intent(),
            _account(),
            orders_submitted_today=-1,
            policy=_policy(),
            checked_at=NOW,
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        PreTradeRiskEngine().assess(
            _intent(),
            _account(),
            orders_submitted_today=0,
            policy=_policy(),
            checked_at=datetime(2026, 8, 12, 9, 0),
        )


@pytest.mark.asyncio
async def test_paper_broker_fills_only_after_a_matching_engine_decision() -> None:
    intent = _intent()
    account = _account()
    decision = PreTradeRiskEngine().assess(
        intent,
        account,
        orders_submitted_today=0,
        policy=_policy(),
        checked_at=NOW,
    )
    approval = PaperTradeApproval(
        intent_id=intent.intent_id,
        risk_decision=decision,
        two_factor_verified=True,
        confirmation_expires_at=NOW.replace(hour=10),
        idempotency_key="risk-engine-approved",
        verified_at=NOW,
    )
    broker = PaperBroker()
    await broker.register_account(account)

    receipt = await broker.submit_order(intent, approval, submitted_at=NOW)

    assert receipt.status is PaperExecutionStatus.FILLED
