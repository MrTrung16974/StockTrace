"""Tests for Phase-9 full-gate paper-only execution simulation."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
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
from stocktrace.domain.entities.pre_trade_risk import (
    PreTradeRiskDecision,
    RiskControlCode,
    RiskViolation,
)
from stocktrace.domain.ports.broker_execution import (
    BrokerOrderNotCancellableError,
)
from stocktrace.domain.ports.paper_execution import PaperExecutionPort
from stocktrace.infrastructure.paper_trading.paper_broker import PaperBroker

NOW = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)


def _intent(
    *,
    intent_id: str = "intent-1",
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
        intent_id=intent_id,
    )


def _approval(
    *,
    intent_id: str = "intent-1",
    key: str = "idem-1",
    risk_approved: bool = True,
    two_factor_verified: bool = True,
    expires_at: datetime = NOW + timedelta(minutes=5),
) -> PaperTradeApproval:
    return PaperTradeApproval(
        intent_id=intent_id,
        risk_decision=PreTradeRiskDecision(
            intent_id=intent_id,
            account_reference="paper-1",
            is_approved=risk_approved,
            violations=()
            if risk_approved
            else (RiskViolation(RiskControlCode.INSUFFICIENT_CASH, "paper-risk-denied"),),
            policy_version="paper-risk-v1",
            checked_at=NOW,
        ),
        two_factor_verified=two_factor_verified,
        confirmation_expires_at=expires_at,
        idempotency_key=key,
        verified_at=NOW,
    )


@pytest.mark.asyncio
async def test_paper_broker_fills_after_simulated_risk_and_2fa_gates() -> None:
    broker = PaperBroker()
    await broker.register_account(PaperAccountSnapshot("paper-1", "owner-1", Decimal("3000000")))

    receipt = await broker.submit(_intent(), _approval(), submitted_at=NOW)
    account = await broker.get_account("paper-1")

    assert receipt.status is PaperExecutionStatus.FILLED
    assert receipt.notional == Decimal("2500000")
    assert account is not None
    assert account.cash_balance == Decimal("500000")
    assert account.positions == (PaperPosition("HPG", 100),)


@pytest.mark.asyncio
async def test_paper_broker_rejects_missing_risk_or_2fa_without_mutating_account() -> None:
    broker = PaperBroker()
    account = PaperAccountSnapshot("paper-1", "owner-1", Decimal("3000000"))
    await broker.register_account(account)

    receipt = await broker.submit(
        _intent(),
        _approval(risk_approved=False, two_factor_verified=False),
        submitted_at=NOW,
    )

    assert receipt.status is PaperExecutionStatus.REJECTED
    assert await broker.get_account("paper-1") == account


@pytest.mark.asyncio
async def test_paper_broker_rejects_expired_confirmation_and_insufficient_balance() -> None:
    broker = PaperBroker()
    await broker.register_account(PaperAccountSnapshot("paper-1", "owner-1", Decimal("1")))

    expired = await broker.submit(
        _intent(),
        _approval(expires_at=NOW - timedelta(seconds=1)),
        submitted_at=NOW,
    )
    insufficient = await broker.submit(
        _intent(intent_id="intent-2"),
        _approval(intent_id="intent-2", key="idem-2"),
        submitted_at=NOW,
    )

    assert expired.status is PaperExecutionStatus.REJECTED
    assert insufficient.status is PaperExecutionStatus.REJECTED


@pytest.mark.asyncio
async def test_paper_broker_idempotency_prevents_double_fill() -> None:
    broker = PaperBroker()
    await broker.register_account(PaperAccountSnapshot("paper-1", "owner-1", Decimal("3000000")))

    first = await broker.submit(_intent(), _approval(), submitted_at=NOW)
    repeated = await broker.submit(_intent(), _approval(), submitted_at=NOW + timedelta(seconds=1))
    account = await broker.get_account("paper-1")

    assert repeated == first
    assert account is not None
    assert account.cash_balance == Decimal("500000")
    assert account.positions == (PaperPosition("HPG", 100),)


@pytest.mark.asyncio
async def test_paper_broker_rejects_risk_decision_for_another_account() -> None:
    broker = PaperBroker()
    await broker.register_account(PaperAccountSnapshot("paper-1", "owner-1", Decimal("3000000")))
    approval = _approval()
    wrong_account_approval = replace(
        approval,
        risk_decision=replace(approval.risk_decision, account_reference="paper-other"),
    )

    receipt = await broker.submit(_intent(), wrong_account_approval, submitted_at=NOW)

    assert receipt.status is PaperExecutionStatus.REJECTED


@pytest.mark.asyncio
async def test_paper_broker_simulates_sell_and_rejects_excess_position() -> None:
    broker = PaperBroker()
    await broker.register_account(
        PaperAccountSnapshot(
            "paper-1",
            "owner-1",
            Decimal("0"),
            (PaperPosition("HPG", 100),),
        ),
    )

    sold = await broker.submit(
        _intent(side=TradeSide.SELL),
        _approval(),
        submitted_at=NOW,
    )
    excess = await broker.submit(
        _intent(intent_id="intent-2", side=TradeSide.SELL, quantity=1),
        _approval(intent_id="intent-2", key="idem-2"),
        submitted_at=NOW,
    )

    assert sold.status is PaperExecutionStatus.FILLED
    assert excess.status is PaperExecutionStatus.REJECTED


@pytest.mark.asyncio
async def test_paper_broker_implements_shared_query_fill_and_cancel_contract() -> None:
    broker: PaperExecutionPort = PaperBroker()
    assert broker.broker_name == "paper"
    await broker.register_account(PaperAccountSnapshot("paper-1", "owner-1", Decimal("3000000")))

    receipt = await broker.submit_order(_intent(), _approval(), submitted_at=NOW)

    assert await broker.get_order(receipt.receipt_id) == receipt
    assert await broker.get_fills(receipt.receipt_id) == (receipt,)
    with pytest.raises(BrokerOrderNotCancellableError):
        await broker.cancel_order(receipt.receipt_id, requested_at=NOW)
