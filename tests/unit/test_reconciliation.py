"""Tests for Phase-15 fill-to-portfolio reconciliation safeguards."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from stocktrace.application.services.reconciliation import ReconciliationService
from stocktrace.domain.entities.investment_suggestion import (
    SuggestionAction,
    TradeIntentDraft,
    TradeSide,
)
from stocktrace.domain.entities.order_lifecycle import OrderFill, OrderLifecycle
from stocktrace.domain.entities.paper_trading import PaperAccountSnapshot, PaperPosition
from stocktrace.domain.entities.reconciliation import (
    PortfolioMutationKind,
    PortfolioPositionSnapshot,
    ReconciliationIssueCode,
    ReconciliationStatus,
)

NOW = datetime(2026, 8, 13, 9, 0, tzinfo=UTC)
POST_BUY_QUANTITY = 120


def _intent(*, side: TradeSide = TradeSide.BUY, quantity: int = 100) -> TradeIntentDraft:
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
        limit_price=Decimal("25000"),
        created_at=NOW,
        intent_id="intent-1",
    )


def _filled_lifecycle(*, side: TradeSide = TradeSide.BUY, quantity: int = 100) -> OrderLifecycle:
    intent = _intent(side=side, quantity=quantity)
    return OrderLifecycle.pending(intent, order_id="order-1").record_fill(
        OrderFill("fill-1", quantity, Decimal("25000"), NOW + timedelta(seconds=1)),
    )


def _portfolio(quantity: int, average_price: Decimal | None) -> PortfolioPositionSnapshot:
    return PortfolioPositionSnapshot(
        owner_id="owner-1",
        symbol="HPG",
        quantity=quantity,
        average_price=average_price,
        captured_at=NOW,
    )


def _broker(quantity: int, *, owner_id: str = "owner-1") -> PaperAccountSnapshot:
    positions = () if quantity == 0 else (PaperPosition("HPG", quantity),)
    return PaperAccountSnapshot("paper-1", owner_id, Decimal("0"), positions)


def test_reconciliation_creates_buy_portfolio_plan_only_when_broker_position_matches() -> None:
    result = ReconciliationService().reconcile(
        _filled_lifecycle(),
        _portfolio(20, Decimal("24000")),
        _broker(POST_BUY_QUANTITY),
        checked_at=NOW + timedelta(seconds=2),
    )

    assert result.status is ReconciliationStatus.MATCHED
    assert result.can_apply_portfolio_mutation is True
    assert result.mutation_plan is not None
    assert result.mutation_plan.kind is PortfolioMutationKind.UPSERT
    assert result.mutation_plan.quantity == POST_BUY_QUANTITY
    assert result.mutation_plan.average_price == Decimal("24833.33333333333333333333333")
    assert result.has_valid_checksum() is True


def test_reconciliation_removes_completed_sell_position_after_matching_broker_snapshot() -> None:
    result = ReconciliationService().reconcile(
        _filled_lifecycle(side=TradeSide.SELL),
        _portfolio(100, Decimal("24000")),
        _broker(0),
        checked_at=NOW + timedelta(seconds=2),
    )

    assert result.status is ReconciliationStatus.MATCHED
    assert result.mutation_plan is not None
    assert result.mutation_plan.kind is PortfolioMutationKind.REMOVE
    assert result.mutation_plan.quantity == 0


def test_reconciliation_never_mutates_portfolio_when_broker_position_disagrees() -> None:
    result = ReconciliationService().reconcile(
        _filled_lifecycle(),
        _portfolio(20, Decimal("24000")),
        _broker(119),
        checked_at=NOW + timedelta(seconds=2),
    )

    assert result.status is ReconciliationStatus.REQUIRES_REVIEW
    assert result.mutation_plan is None
    assert ReconciliationIssueCode.BROKER_POSITION_MISMATCH in result.issues


def test_reconciliation_keeps_portfolio_unchanged_for_rejected_order() -> None:
    lifecycle = OrderLifecycle.pending(_intent(), order_id="order-1").reject(
        reason="broker rejected",
        at=NOW + timedelta(seconds=1),
    )
    result = ReconciliationService().reconcile(
        lifecycle,
        _portfolio(20, Decimal("24000")),
        _broker(20),
        checked_at=NOW + timedelta(seconds=2),
    )

    assert result.status is ReconciliationStatus.MATCHED
    assert result.mutation_plan is None
    assert result.can_apply_portfolio_mutation is False


def test_reconciliation_requires_review_for_broker_owner_or_sell_quantity_mismatch() -> None:
    owner_mismatch = ReconciliationService().reconcile(
        _filled_lifecycle(),
        _portfolio(0, None),
        _broker(100, owner_id="other-owner"),
        checked_at=NOW + timedelta(seconds=2),
    )
    sell_overflow = ReconciliationService().reconcile(
        _filled_lifecycle(side=TradeSide.SELL, quantity=100),
        _portfolio(50, Decimal("24000")),
        _broker(50),
        checked_at=NOW + timedelta(seconds=2),
    )

    assert ReconciliationIssueCode.BROKER_OWNER_MISMATCH in owner_mismatch.issues
    assert ReconciliationIssueCode.SELL_QUANTITY_EXCEEDS_PORTFOLIO in sell_overflow.issues
