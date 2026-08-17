"""Immutable order lifecycle state machine for confirmed execution reports."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from stocktrace.domain.entities.investment_suggestion import TradeIntentDraft, TradeSide
from stocktrace.domain.entities.paper_trading import PaperExecutionReceipt, PaperExecutionStatus


class OrderLifecycleStatus(StrEnum):
    """All externally visible stages of an order after broker submission."""

    PENDING = "PENDING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class OrderFill:
    """One immutable, broker-confirmed fill; no inference is permitted."""

    fill_id: str
    quantity: int
    price: Decimal
    occurred_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.fill_id, "fill_id")
        if self.quantity <= 0:
            raise ValueError("fill quantity must be greater than zero.")
        if self.price <= 0:
            raise ValueError("fill price must be greater than zero.")
        _require_aware_time(self.occurred_at, "occurred_at")


@dataclass(frozen=True, slots=True)
class OrderLifecycle:
    """Checksum-protected lifecycle snapshot with validated state transitions."""

    order_id: str
    intent_id: str
    owner_id: str
    account_reference: str
    symbol: str
    side: TradeSide
    requested_quantity: int
    status: OrderLifecycleStatus
    fills: tuple[OrderFill, ...]
    created_at: datetime
    updated_at: datetime
    terminal_reason: str | None
    checksum: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.order_id, "order_id"),
            (self.intent_id, "intent_id"),
            (self.owner_id, "owner_id"),
            (self.account_reference, "account_reference"),
            (self.symbol, "symbol"),
        ):
            _require_text(value, field_name)
        if self.quantity_filled > self.requested_quantity:
            raise ValueError("filled quantity must not exceed requested_quantity.")
        if len({fill.fill_id for fill in self.fills}) != len(self.fills):
            raise ValueError("fills must have unique fill_id values.")
        _require_aware_time(self.created_at, "created_at")
        _require_aware_time(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at.")
        if not _CHECKSUM_PATTERN.fullmatch(self.checksum):
            raise ValueError("checksum must be a lowercase SHA-256 hex digest.")
        _validate_status_invariants(self)

    @classmethod
    def pending(cls, intent: TradeIntentDraft, *, order_id: str | None = None) -> OrderLifecycle:
        """Create an unfilled lifecycle before the broker reports a terminal outcome."""
        return cls._create(
            order_id=order_id or str(uuid4()),
            intent=intent,
            status=OrderLifecycleStatus.PENDING,
            fills=(),
            created_at=intent.created_at,
            updated_at=intent.created_at,
            terminal_reason=None,
        )

    @classmethod
    def from_paper_receipt(
        cls,
        intent: TradeIntentDraft,
        receipt: PaperExecutionReceipt,
    ) -> OrderLifecycle:
        """Map the paper adapter's explicit terminal receipt through this state machine."""
        if receipt.intent_id != intent.intent_id:
            raise ValueError("receipt must belong to the lifecycle intent.")
        if receipt.account_reference != intent.account_reference:
            raise ValueError("receipt must belong to the lifecycle account.")
        lifecycle = cls.pending(intent, order_id=receipt.receipt_id)
        if receipt.status is PaperExecutionStatus.REJECTED:
            return lifecycle.reject(
                reason=receipt.reason or "paper order rejected.",
                at=receipt.created_at,
            )
        if receipt.fill_price is None:
            raise ValueError("filled paper receipt unexpectedly lacks fill_price.")
        return lifecycle.record_fill(
            OrderFill(
                fill_id=receipt.receipt_id,
                quantity=receipt.filled_quantity,
                price=receipt.fill_price,
                occurred_at=receipt.created_at,
            ),
        )

    @property
    def quantity_filled(self) -> int:
        """Return the confirmed cumulative fill quantity."""
        return sum(fill.quantity for fill in self.fills)

    @property
    def average_fill_price(self) -> Decimal | None:
        """Return the weighted average confirmed fill price, if any."""
        if not self.fills:
            return None
        return (
            sum((fill.price * fill.quantity for fill in self.fills), Decimal("0"))
            / self.quantity_filled
        )

    @property
    def is_terminal(self) -> bool:
        """Return whether this lifecycle can no longer accept state changes."""
        return self.status in {
            OrderLifecycleStatus.FILLED,
            OrderLifecycleStatus.REJECTED,
            OrderLifecycleStatus.CANCELLED,
        }

    def record_fill(self, fill: OrderFill) -> OrderLifecycle:
        """Apply one fill, allowing only pending/partial orders and exact retries."""
        existing = next((item for item in self.fills if item.fill_id == fill.fill_id), None)
        if existing is not None:
            if existing == fill:
                return self
            raise ValueError("fill_id is already bound to different fill data.")
        if self.status not in {OrderLifecycleStatus.PENDING, OrderLifecycleStatus.PARTIALLY_FILLED}:
            raise ValueError("terminal order cannot receive a fill.")
        if fill.occurred_at < self.updated_at:
            raise ValueError("fill timestamp must not precede the prior lifecycle update.")
        fills = (*self.fills, fill)
        total = sum(item.quantity for item in fills)
        if total > self.requested_quantity:
            raise ValueError("fill quantity would exceed requested_quantity.")
        status = (
            OrderLifecycleStatus.FILLED
            if total == self.requested_quantity
            else OrderLifecycleStatus.PARTIALLY_FILLED
        )
        return self._replace(
            status=status,
            fills=fills,
            updated_at=fill.occurred_at,
            terminal_reason=None,
        )

    def reject(self, *, reason: str, at: datetime) -> OrderLifecycle:
        """Mark an entirely unfilled pending order rejected by the broker."""
        _require_text(reason, "reason")
        _require_aware_time(at, "at")
        if self.status is OrderLifecycleStatus.REJECTED:
            return self
        if self.status is not OrderLifecycleStatus.PENDING:
            raise ValueError("only an unfilled pending order can be rejected.")
        if at < self.updated_at:
            raise ValueError("rejection timestamp must not precede the prior lifecycle update.")
        return self._replace(
            status=OrderLifecycleStatus.REJECTED,
            updated_at=at,
            terminal_reason=reason,
        )

    def cancel(self, *, reason: str, at: datetime) -> OrderLifecycle:
        """Cancel the unfilled remainder of a pending or partially filled order."""
        _require_text(reason, "reason")
        _require_aware_time(at, "at")
        if self.status is OrderLifecycleStatus.CANCELLED:
            return self
        if self.status not in {OrderLifecycleStatus.PENDING, OrderLifecycleStatus.PARTIALLY_FILLED}:
            raise ValueError("only pending or partially filled order can be cancelled.")
        if at < self.updated_at:
            raise ValueError("cancellation timestamp must not precede the prior lifecycle update.")
        return self._replace(
            status=OrderLifecycleStatus.CANCELLED,
            updated_at=at,
            terminal_reason=reason,
        )

    def has_valid_checksum(self) -> bool:
        """Return whether lifecycle fields still match their audit checksum."""
        return self.checksum == _checksum_for(self)

    @classmethod
    def _create(
        cls,
        *,
        order_id: str,
        intent: TradeIntentDraft,
        status: OrderLifecycleStatus,
        fills: tuple[OrderFill, ...],
        created_at: datetime,
        updated_at: datetime,
        terminal_reason: str | None,
    ) -> OrderLifecycle:
        snapshot = cls(
            order_id=order_id,
            intent_id=intent.intent_id,
            owner_id=intent.owner_id,
            account_reference=intent.account_reference,
            symbol=intent.symbol,
            side=intent.side,
            requested_quantity=intent.quantity,
            status=status,
            fills=fills,
            created_at=created_at,
            updated_at=updated_at,
            terminal_reason=terminal_reason,
            checksum="0" * 64,
        )
        return cls._with_checksum(snapshot)

    def _replace(
        self,
        *,
        status: OrderLifecycleStatus,
        fills: tuple[OrderFill, ...] | None = None,
        updated_at: datetime,
        terminal_reason: str | None,
    ) -> OrderLifecycle:
        snapshot = OrderLifecycle(
            order_id=self.order_id,
            intent_id=self.intent_id,
            owner_id=self.owner_id,
            account_reference=self.account_reference,
            symbol=self.symbol,
            side=self.side,
            requested_quantity=self.requested_quantity,
            status=status,
            fills=self.fills if fills is None else fills,
            created_at=self.created_at,
            updated_at=updated_at,
            terminal_reason=terminal_reason,
            checksum="0" * 64,
        )
        return self._with_checksum(snapshot)

    @classmethod
    def _with_checksum(cls, snapshot: OrderLifecycle) -> OrderLifecycle:
        return cls(
            order_id=snapshot.order_id,
            intent_id=snapshot.intent_id,
            owner_id=snapshot.owner_id,
            account_reference=snapshot.account_reference,
            symbol=snapshot.symbol,
            side=snapshot.side,
            requested_quantity=snapshot.requested_quantity,
            status=snapshot.status,
            fills=snapshot.fills,
            created_at=snapshot.created_at,
            updated_at=snapshot.updated_at,
            terminal_reason=snapshot.terminal_reason,
            checksum=_checksum_for(snapshot),
        )


_CHECKSUM_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def _validate_status_invariants(lifecycle: OrderLifecycle) -> None:  # noqa: PLR0912
    if lifecycle.requested_quantity <= 0:
        raise ValueError("requested_quantity must be greater than zero.")
    if lifecycle.status is OrderLifecycleStatus.PENDING:
        if lifecycle.fills or lifecycle.terminal_reason is not None:
            raise ValueError("pending order must not have fills or terminal_reason.")
        return
    if lifecycle.status is OrderLifecycleStatus.PARTIALLY_FILLED:
        if not 0 < lifecycle.quantity_filled < lifecycle.requested_quantity:
            raise ValueError("partially filled order requires a partial fill quantity.")
        if lifecycle.terminal_reason is not None:
            raise ValueError("partially filled order must not have terminal_reason.")
        return
    if lifecycle.status is OrderLifecycleStatus.FILLED:
        if lifecycle.quantity_filled != lifecycle.requested_quantity:
            raise ValueError("filled order requires its complete requested quantity.")
        if lifecycle.terminal_reason is not None:
            raise ValueError("filled order must not have terminal_reason.")
        return
    if lifecycle.status is OrderLifecycleStatus.REJECTED:
        if lifecycle.fills or not lifecycle.terminal_reason:
            raise ValueError("rejected order requires reason and cannot have fills.")
        return
    if lifecycle.status is OrderLifecycleStatus.CANCELLED:
        if (
            lifecycle.quantity_filled >= lifecycle.requested_quantity
            or not lifecycle.terminal_reason
        ):
            raise ValueError("cancelled order requires reason and an unfilled remainder.")
        return
    raise ValueError("status must be an OrderLifecycleStatus.")


def _checksum_for(lifecycle: OrderLifecycle) -> str:
    payload = {
        "account_reference": lifecycle.account_reference,
        "checksum_version": 1,
        "created_at": lifecycle.created_at.isoformat(),
        "fills": [
            {
                "fill_id": fill.fill_id,
                "occurred_at": fill.occurred_at.isoformat(),
                "price": str(fill.price),
                "quantity": fill.quantity,
            }
            for fill in lifecycle.fills
        ],
        "intent_id": lifecycle.intent_id,
        "order_id": lifecycle.order_id,
        "owner_id": lifecycle.owner_id,
        "requested_quantity": lifecycle.requested_quantity,
        "side": lifecycle.side.value,
        "status": lifecycle.status.value,
        "symbol": lifecycle.symbol,
        "terminal_reason": lifecycle.terminal_reason,
        "updated_at": lifecycle.updated_at.isoformat(),
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty.")


def _require_aware_time(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
