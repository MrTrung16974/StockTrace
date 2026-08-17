"""Paper-only trade execution contracts with simulated risk and confirmation gates."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from stocktrace.domain.entities.pre_trade_risk import PreTradeRiskDecision


class PaperExecutionStatus(StrEnum):
    """Terminal result of a paper-only simulated submission."""

    FILLED = "FILLED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class PaperPosition:
    """A positive simulated position held in a paper account."""

    symbol: str
    quantity: int

    def __post_init__(self) -> None:
        _require_text(self.symbol, "symbol")
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero.")


@dataclass(frozen=True, slots=True)
class PaperAccountSnapshot:
    """Paper-only account state; it contains no broker credential or secret."""

    account_reference: str
    owner_id: str
    cash_balance: Decimal
    positions: tuple[PaperPosition, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.account_reference, "account_reference")
        _require_text(self.owner_id, "owner_id")
        if self.cash_balance < 0:
            raise ValueError("cash_balance must not be negative.")
        symbols = tuple(position.symbol for position in self.positions)
        if len(set(symbols)) != len(symbols):
            raise ValueError("positions must not contain duplicate symbols.")


@dataclass(frozen=True, slots=True)
class PaperTradeApproval:
    """Simulated prerequisites that mirror later risk and secure-UI checks."""

    intent_id: str
    risk_decision: PreTradeRiskDecision
    two_factor_verified: bool
    confirmation_expires_at: datetime
    idempotency_key: str
    verified_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        _require_text(self.intent_id, "intent_id")
        _require_text(self.idempotency_key, "idempotency_key")
        _require_aware_time(self.confirmation_expires_at, "confirmation_expires_at")
        _require_aware_time(self.verified_at, "verified_at")
        if self.risk_decision.intent_id != self.intent_id:
            raise ValueError("risk_decision must belong to the approval intent.")

    def is_valid_at(self, submitted_at: datetime) -> bool:
        """Return whether fake 2FA is verified and has not expired at submission time."""
        _require_aware_time(submitted_at, "submitted_at")
        return (
            self.risk_decision.is_approved
            and self.two_factor_verified
            and submitted_at <= self.confirmation_expires_at
        )


@dataclass(frozen=True, slots=True)
class PaperExecutionReceipt:
    """Immutable record of a simulated execution; never a real broker response."""

    receipt_id: str
    account_reference: str
    intent_id: str
    idempotency_key: str
    status: PaperExecutionStatus
    filled_quantity: int
    fill_price: Decimal | None
    notional: Decimal
    reason: str | None
    created_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.receipt_id, "receipt_id")
        _require_text(self.account_reference, "account_reference")
        _require_text(self.intent_id, "intent_id")
        _require_text(self.idempotency_key, "idempotency_key")
        _require_aware_time(self.created_at, "created_at")
        if self.status is PaperExecutionStatus.FILLED:
            if self.filled_quantity <= 0 or self.fill_price is None or self.fill_price <= 0:
                raise ValueError("filled receipt requires positive quantity and fill_price.")
            if self.notional != self.fill_price * self.filled_quantity:
                raise ValueError("filled receipt notional must equal fill_price times quantity.")
            if self.reason is not None:
                raise ValueError("filled receipt must not carry a rejection reason.")
            return
        if self.filled_quantity != 0 or self.fill_price is not None or self.notional != 0:
            raise ValueError("rejected receipt must not carry a fill.")
        _require_text(self.reason or "", "reason")


def new_paper_receipt_id() -> str:
    """Generate an opaque identifier for one simulated execution receipt."""
    return str(uuid4())


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty.")


def _require_aware_time(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
