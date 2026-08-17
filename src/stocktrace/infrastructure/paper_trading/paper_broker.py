"""In-memory paper broker that cannot send a real order."""

from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal

from stocktrace.domain.entities.investment_suggestion import TradeIntentDraft, TradeSide
from stocktrace.domain.entities.paper_trading import (
    PaperAccountSnapshot,
    PaperExecutionReceipt,
    PaperExecutionStatus,
    PaperPosition,
    PaperTradeApproval,
    new_paper_receipt_id,
)
from stocktrace.domain.ports.broker_execution import (
    BrokerOrderNotCancellableError,
    BrokerOrderNotFoundError,
)


class PaperBroker:
    """Simulate full-gate paper fills in memory, with no SDK, HTTP, or secrets."""

    def __init__(self) -> None:
        self._accounts: dict[str, PaperAccountSnapshot] = {}
        self._receipts_by_key: dict[tuple[str, str], PaperExecutionReceipt] = {}
        self._receipts_by_id: dict[str, PaperExecutionReceipt] = {}
        self._lock = asyncio.Lock()

    @property
    def broker_name(self) -> str:
        """Return a stable paper-only identifier; this is never a real broker name."""
        return "paper"

    async def register_account(self, account: PaperAccountSnapshot) -> None:
        """Register a fresh paper account; replacing existing state is forbidden."""
        async with self._lock:
            if account.account_reference in self._accounts:
                raise ValueError("paper account is already registered.")
            self._accounts[account.account_reference] = account

    async def get_account(self, account_reference: str) -> PaperAccountSnapshot | None:
        """Return the local paper account snapshot, if present."""
        async with self._lock:
            return self._accounts.get(account_reference)

    async def submit(
        self,
        intent: TradeIntentDraft,
        approval: PaperTradeApproval,
        *,
        submitted_at: datetime,
    ) -> PaperExecutionReceipt:
        """Fill at the draft limit price only after simulated risk and 2FA gates pass."""
        return await self.submit_order(intent, approval, submitted_at=submitted_at)

    async def submit_order(
        self,
        intent: TradeIntentDraft,
        approval: PaperTradeApproval,
        *,
        submitted_at: datetime,
    ) -> PaperExecutionReceipt:
        """Implement the shared broker port with an in-memory paper-only fill."""
        _require_aware_time(submitted_at)
        async with self._lock:
            key = (intent.account_reference, approval.idempotency_key)
            existing = self._receipts_by_key.get(key)
            if existing is not None:
                if existing.intent_id == intent.intent_id:
                    return existing
                return self._reject(
                    intent,
                    approval,
                    submitted_at,
                    "idempotency key is already bound to another intent.",
                )

            account = self._accounts.get(intent.account_reference)
            rejection_reason = _submission_rejection_reason(
                account,
                intent,
                approval,
                submitted_at,
            )
            if rejection_reason is not None:
                return self._record_rejection(
                    intent,
                    approval,
                    submitted_at,
                    rejection_reason,
                )

            notional = intent.limit_price * intent.quantity
            if account is None:
                raise RuntimeError("validated paper account unexpectedly missing.")
            if intent.side is TradeSide.BUY:
                updated_account = _apply_buy(account, intent.symbol, intent.quantity, notional)
            else:
                updated_account = _apply_sell(account, intent.symbol, intent.quantity, notional)

            self._accounts[account.account_reference] = updated_account
            receipt = PaperExecutionReceipt(
                receipt_id=new_paper_receipt_id(),
                account_reference=intent.account_reference,
                intent_id=intent.intent_id,
                idempotency_key=approval.idempotency_key,
                status=PaperExecutionStatus.FILLED,
                filled_quantity=intent.quantity,
                fill_price=intent.limit_price,
                notional=notional,
                reason=None,
                created_at=submitted_at,
            )
            self._receipts_by_key[key] = receipt
            self._receipts_by_id[receipt.receipt_id] = receipt
            return receipt

    async def cancel_order(
        self,
        order_id: str,
        *,
        requested_at: datetime,
    ) -> PaperExecutionReceipt:
        """Fail explicitly: PaperBroker fills/rejects immediately, so no order is open."""
        _require_aware_time(requested_at)
        async with self._lock:
            if order_id not in self._receipts_by_id:
                raise BrokerOrderNotFoundError("paper order was not found.")
            raise BrokerOrderNotCancellableError("paper order is already in a terminal state.")

    async def get_order(self, order_id: str) -> PaperExecutionReceipt | None:
        """Return the recorded paper outcome for one local order identifier."""
        async with self._lock:
            return self._receipts_by_id.get(order_id)

    async def get_fills(self, order_id: str) -> tuple[PaperExecutionReceipt, ...]:
        """Return the immediate fill receipt only when a paper order filled."""
        async with self._lock:
            receipt = self._receipts_by_id.get(order_id)
            if receipt is None or receipt.status is not PaperExecutionStatus.FILLED:
                return ()
            return (receipt,)

    def _record_rejection(
        self,
        intent: TradeIntentDraft,
        approval: PaperTradeApproval,
        submitted_at: datetime,
        reason: str,
    ) -> PaperExecutionReceipt:
        receipt = self._reject(intent, approval, submitted_at, reason)
        self._receipts_by_key[(intent.account_reference, approval.idempotency_key)] = receipt
        self._receipts_by_id[receipt.receipt_id] = receipt
        return receipt

    @staticmethod
    def _reject(
        intent: TradeIntentDraft,
        approval: PaperTradeApproval,
        submitted_at: datetime,
        reason: str,
    ) -> PaperExecutionReceipt:
        return PaperExecutionReceipt(
            receipt_id=new_paper_receipt_id(),
            account_reference=intent.account_reference,
            intent_id=intent.intent_id,
            idempotency_key=approval.idempotency_key,
            status=PaperExecutionStatus.REJECTED,
            filled_quantity=0,
            fill_price=None,
            notional=Decimal("0"),
            reason=reason,
            created_at=submitted_at,
        )


def _apply_buy(
    account: PaperAccountSnapshot,
    symbol: str,
    quantity: int,
    notional: Decimal,
) -> PaperAccountSnapshot:
    positions = _position_map(account)
    positions[symbol] = positions.get(symbol, 0) + quantity
    return _account_from_positions(account, account.cash_balance - notional, positions)


def _submission_rejection_reason(
    account: PaperAccountSnapshot | None,
    intent: TradeIntentDraft,
    approval: PaperTradeApproval,
    submitted_at: datetime,
) -> str | None:
    if account is None:
        return "paper account is not registered."
    reason: str | None = None
    if account.owner_id != intent.owner_id:
        reason = "intent owner does not match the paper account owner."
    elif approval.intent_id != intent.intent_id:
        reason = "approval does not belong to this intent."
    elif approval.risk_decision.account_reference != intent.account_reference:
        reason = "risk decision does not belong to this paper account."
    elif not approval.is_valid_at(submitted_at):
        reason = "paper risk approval or simulated 2FA confirmation is invalid or expired."
    else:
        notional = intent.limit_price * intent.quantity
        if intent.side is TradeSide.BUY and account.cash_balance < notional:
            reason = "insufficient paper cash balance."
        elif (
            intent.side is TradeSide.SELL
            and _position_quantity(account, intent.symbol) < intent.quantity
        ):
            reason = "insufficient paper position."
    return reason


def _apply_sell(
    account: PaperAccountSnapshot,
    symbol: str,
    quantity: int,
    notional: Decimal,
) -> PaperAccountSnapshot:
    positions = _position_map(account)
    remaining = positions[symbol] - quantity
    if remaining:
        positions[symbol] = remaining
    else:
        del positions[symbol]
    return _account_from_positions(account, account.cash_balance + notional, positions)


def _position_quantity(account: PaperAccountSnapshot, symbol: str) -> int:
    return _position_map(account).get(symbol, 0)


def _position_map(account: PaperAccountSnapshot) -> dict[str, int]:
    return {position.symbol: position.quantity for position in account.positions}


def _account_from_positions(
    account: PaperAccountSnapshot,
    cash_balance: Decimal,
    positions: dict[str, int],
) -> PaperAccountSnapshot:
    return PaperAccountSnapshot(
        account_reference=account.account_reference,
        owner_id=account.owner_id,
        cash_balance=cash_balance,
        positions=tuple(
            PaperPosition(symbol=symbol, quantity=quantity)
            for symbol, quantity in sorted(positions.items())
        ),
    )


def _require_aware_time(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("submitted_at must be timezone-aware.")
