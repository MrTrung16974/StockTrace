"""Phase-17 security, concurrency, and broker-outage safeguards for paper trading."""

from __future__ import annotations

import asyncio
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
from stocktrace.domain.entities.pre_trade_risk import PreTradeRiskDecision
from stocktrace.domain.ports.broker_execution import BrokerIntegrationNotConfiguredError
from stocktrace.infrastructure.brokers.official_broker_skeleton import OfficialBrokerSkeleton
from stocktrace.infrastructure.paper_trading.paper_broker import PaperBroker

NOW = datetime(2026, 8, 13, 9, 0, tzinfo=UTC)
CONCURRENT_SUBMISSIONS = 20


def _intent() -> TradeIntentDraft:
    return TradeIntentDraft(
        owner_id="owner-1",
        account_reference="paper-1",
        suggestion_id="suggestion-1",
        symbol="HPG",
        suggestion_action=SuggestionAction.ACCUMULATE_CONDITIONALLY,
        side=TradeSide.BUY,
        quantity=100,
        limit_price=Decimal("25000"),
        created_at=NOW,
        intent_id="intent-1",
    )


def _approval() -> PaperTradeApproval:
    return PaperTradeApproval(
        intent_id="intent-1",
        risk_decision=PreTradeRiskDecision(
            intent_id="intent-1",
            account_reference="paper-1",
            is_approved=True,
            violations=(),
            policy_version="risk-v1",
            checked_at=NOW,
        ),
        two_factor_verified=True,
        confirmation_expires_at=NOW + timedelta(minutes=5),
        idempotency_key="shared-idempotency-key",
        verified_at=NOW,
    )


@pytest.mark.asyncio
async def test_concurrent_duplicate_paper_submissions_fill_once() -> None:
    broker = PaperBroker()
    await broker.register_account(PaperAccountSnapshot("paper-1", "owner-1", Decimal("3000000")))
    intent = _intent()
    approval = _approval()

    receipts = await asyncio.gather(
        *(
            broker.submit_order(intent, approval, submitted_at=NOW + timedelta(seconds=index))
            for index in range(CONCURRENT_SUBMISSIONS)
        ),
    )
    account = await broker.get_account("paper-1")

    assert {receipt.receipt_id for receipt in receipts} == {receipts[0].receipt_id}
    assert receipts[0].status is PaperExecutionStatus.FILLED
    assert account is not None
    assert account.cash_balance == Decimal("500000")
    assert account.positions == (PaperPosition("HPG", 100),)


@pytest.mark.asyncio
async def test_unapproved_broker_outage_fails_closed_without_any_submission_path() -> None:
    broker = OfficialBrokerSkeleton("unapproved-candidate")

    with pytest.raises(BrokerIntegrationNotConfiguredError, match="official API contract"):
        await broker.submit_order(_intent(), _approval(), submitted_at=NOW)
    with pytest.raises(BrokerIntegrationNotConfiguredError):
        await broker.get_order("unknown-order")
