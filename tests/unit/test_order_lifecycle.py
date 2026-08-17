"""Tests for the Phase-15 immutable order lifecycle state machine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from stocktrace.domain.entities.investment_suggestion import (
    SuggestionAction,
    TradeIntentDraft,
    TradeSide,
)
from stocktrace.domain.entities.order_lifecycle import (
    OrderFill,
    OrderLifecycle,
    OrderLifecycleStatus,
)
from stocktrace.domain.entities.paper_trading import (
    PaperExecutionReceipt,
    PaperExecutionStatus,
)

NOW = datetime(2026, 8, 13, 9, 0, tzinfo=UTC)
FULL_QUANTITY = 100
PARTIAL_QUANTITY = 40


def _intent(*, quantity: int = FULL_QUANTITY) -> TradeIntentDraft:
    return TradeIntentDraft(
        owner_id="owner-1",
        account_reference="paper-1",
        suggestion_id="suggestion-1",
        symbol="HPG",
        suggestion_action=SuggestionAction.ACCUMULATE_CONDITIONALLY,
        side=TradeSide.BUY,
        quantity=quantity,
        limit_price=Decimal("25000"),
        created_at=NOW,
        intent_id="intent-1",
    )


def test_order_lifecycle_accepts_only_valid_fill_state_transitions() -> None:
    lifecycle = OrderLifecycle.pending(_intent(), order_id="order-1")
    partial = lifecycle.record_fill(
        OrderFill("fill-1", PARTIAL_QUANTITY, Decimal("25000"), NOW + timedelta(seconds=1)),
    )
    filled = partial.record_fill(
        OrderFill(
            "fill-2",
            FULL_QUANTITY - PARTIAL_QUANTITY,
            Decimal("26000"),
            NOW + timedelta(seconds=2),
        ),
    )

    assert lifecycle.status is OrderLifecycleStatus.PENDING
    assert partial.status is OrderLifecycleStatus.PARTIALLY_FILLED
    assert filled.status is OrderLifecycleStatus.FILLED
    assert filled.quantity_filled == FULL_QUANTITY
    assert filled.average_fill_price == Decimal("25600")
    assert filled.has_valid_checksum() is True
    assert partial.record_fill(partial.fills[0]) == partial
    with pytest.raises(ValueError, match="terminal order"):
        filled.record_fill(OrderFill("fill-3", 1, Decimal("25000"), NOW + timedelta(seconds=3)))


def test_order_lifecycle_allows_partial_cancel_but_not_rejection_after_fill() -> None:
    lifecycle = OrderLifecycle.pending(_intent(), order_id="order-1")
    partial = lifecycle.record_fill(
        OrderFill("fill-1", PARTIAL_QUANTITY, Decimal("25000"), NOW + timedelta(seconds=1)),
    )
    cancelled = partial.cancel(
        reason="broker cancelled remaining quantity",
        at=NOW + timedelta(seconds=2),
    )

    assert cancelled.status is OrderLifecycleStatus.CANCELLED
    assert cancelled.quantity_filled == PARTIAL_QUANTITY
    assert cancelled.terminal_reason == "broker cancelled remaining quantity"
    with pytest.raises(ValueError, match="only an unfilled pending"):
        partial.reject(reason="not valid after partial fill", at=NOW + timedelta(seconds=2))


def test_paper_receipts_map_to_explicit_filled_or_rejected_lifecycle() -> None:
    intent = _intent()
    filled_receipt = PaperExecutionReceipt(
        receipt_id="receipt-filled",
        account_reference="paper-1",
        intent_id="intent-1",
        idempotency_key="idempotency-1",
        status=PaperExecutionStatus.FILLED,
        filled_quantity=100,
        fill_price=Decimal("25000"),
        notional=Decimal("2500000"),
        reason=None,
        created_at=NOW + timedelta(seconds=1),
    )
    rejected_receipt = PaperExecutionReceipt(
        receipt_id="receipt-rejected",
        account_reference="paper-1",
        intent_id="intent-1",
        idempotency_key="idempotency-2",
        status=PaperExecutionStatus.REJECTED,
        filled_quantity=0,
        fill_price=None,
        notional=Decimal("0"),
        reason="risk control denied",
        created_at=NOW + timedelta(seconds=1),
    )

    filled = OrderLifecycle.from_paper_receipt(intent, filled_receipt)
    rejected = OrderLifecycle.from_paper_receipt(intent, rejected_receipt)

    assert filled.status is OrderLifecycleStatus.FILLED
    assert filled.order_id == "receipt-filled"
    assert rejected.status is OrderLifecycleStatus.REJECTED
    assert rejected.terminal_reason == "risk control denied"
