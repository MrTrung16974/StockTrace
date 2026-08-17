"""Fail-closed reconciliation of confirmed fills with broker account snapshots."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from stocktrace.domain.entities.investment_suggestion import TradeSide
from stocktrace.domain.entities.order_lifecycle import OrderLifecycle
from stocktrace.domain.entities.paper_trading import PaperAccountSnapshot
from stocktrace.domain.entities.reconciliation import (
    PortfolioMutationKind,
    PortfolioMutationPlan,
    PortfolioPositionSnapshot,
    ReconciliationIssueCode,
    ReconciliationResult,
)


class ReconciliationService:
    """Produce a mutation plan only when broker position equals expected fill outcome.

    The caller must persist the result and apply its plan transactionally exactly once.
    This pure service deliberately has no access to Telegram or a broker submit method.
    """

    def reconcile(
        self,
        lifecycle: OrderLifecycle,
        portfolio_before: PortfolioPositionSnapshot,
        broker_account_after: PaperAccountSnapshot,
        *,
        checked_at: datetime,
    ) -> ReconciliationResult:
        """Compare exact confirmed fills with broker state and create an update plan."""
        _require_aware_time(checked_at)
        issues = _identity_issues(lifecycle, portfolio_before, broker_account_after)
        plan = None
        if not issues:
            plan, expected_quantity, position_issue = _expected_mutation(
                lifecycle,
                portfolio_before,
            )
            if position_issue is not None:
                issues.append(position_issue)
            elif _broker_quantity(broker_account_after, lifecycle.symbol) != expected_quantity:
                issues.append(ReconciliationIssueCode.BROKER_POSITION_MISMATCH)
        return ReconciliationResult.create(
            order_id=lifecycle.order_id,
            lifecycle_checksum=lifecycle.checksum,
            account_reference=lifecycle.account_reference,
            owner_id=lifecycle.owner_id,
            symbol=lifecycle.symbol,
            issues=tuple(issues),
            mutation_plan=plan,
            checked_at=checked_at,
        )


def _identity_issues(
    lifecycle: OrderLifecycle,
    portfolio: PortfolioPositionSnapshot,
    broker_account: PaperAccountSnapshot,
) -> list[ReconciliationIssueCode]:
    issues: list[ReconciliationIssueCode] = []
    if portfolio.owner_id != lifecycle.owner_id or portfolio.symbol != lifecycle.symbol:
        issues.append(ReconciliationIssueCode.PORTFOLIO_OWNER_MISMATCH)
    if broker_account.account_reference != lifecycle.account_reference:
        issues.append(ReconciliationIssueCode.BROKER_ACCOUNT_MISMATCH)
    if broker_account.owner_id != lifecycle.owner_id:
        issues.append(ReconciliationIssueCode.BROKER_OWNER_MISMATCH)
    return issues


def _expected_mutation(
    lifecycle: OrderLifecycle,
    portfolio: PortfolioPositionSnapshot,
) -> tuple[PortfolioMutationPlan | None, int, ReconciliationIssueCode | None]:
    filled_quantity = lifecycle.quantity_filled
    if filled_quantity == 0:
        return None, portfolio.quantity, None
    if lifecycle.side is TradeSide.BUY:
        quantity = portfolio.quantity + filled_quantity
        average_price = _buy_average_price(portfolio, lifecycle)
        return (
            PortfolioMutationPlan(
                kind=PortfolioMutationKind.UPSERT,
                owner_id=lifecycle.owner_id,
                symbol=lifecycle.symbol,
                quantity=quantity,
                average_price=average_price,
            ),
            quantity,
            None,
        )
    if filled_quantity > portfolio.quantity:
        return (
            PortfolioMutationPlan(
                kind=PortfolioMutationKind.REMOVE,
                owner_id=lifecycle.owner_id,
                symbol=lifecycle.symbol,
                quantity=0,
                average_price=None,
            ),
            portfolio.quantity,
            ReconciliationIssueCode.SELL_QUANTITY_EXCEEDS_PORTFOLIO,
        )
    quantity = portfolio.quantity - filled_quantity
    if quantity == 0:
        return (
            PortfolioMutationPlan(
                kind=PortfolioMutationKind.REMOVE,
                owner_id=lifecycle.owner_id,
                symbol=lifecycle.symbol,
                quantity=0,
                average_price=None,
            ),
            quantity,
            None,
        )
    return (
        PortfolioMutationPlan(
            kind=PortfolioMutationKind.UPSERT,
            owner_id=lifecycle.owner_id,
            symbol=lifecycle.symbol,
            quantity=quantity,
            average_price=portfolio.average_price,
        ),
        quantity,
        None,
    )


def _buy_average_price(portfolio: PortfolioPositionSnapshot, lifecycle: OrderLifecycle) -> Decimal:
    if lifecycle.quantity_filled == 0:
        if portfolio.average_price is None:
            raise ValueError("empty buy baseline cannot produce an upsert mutation without fills.")
        return portfolio.average_price
    fill_average = lifecycle.average_fill_price
    if fill_average is None:
        raise ValueError("filled lifecycle unexpectedly lacks average fill price.")
    current_notional = portfolio.quantity * (portfolio.average_price or Decimal("0"))
    fill_notional = lifecycle.quantity_filled * fill_average
    return (current_notional + fill_notional) / (portfolio.quantity + lifecycle.quantity_filled)


def _broker_quantity(account: PaperAccountSnapshot, symbol: str) -> int:
    return next(
        (position.quantity for position in account.positions if position.symbol == symbol),
        0,
    )


def _require_aware_time(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("checked_at must be timezone-aware.")
