"""Paper-only secure confirmation state for a pre-approved trade intent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from stocktrace.domain.entities.investment_suggestion import TradeIntentDraft
from stocktrace.domain.entities.pre_trade_risk import PreTradeRiskDecision


class PaperConfirmationStatus(StrEnum):
    """Lifecycle states for a secure-paper-confirmation request."""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class PaperTradeConfirmation:
    """Immutable snapshot a secure UI must show before paper submission.

    It has no broker credential and is never created for a failed risk decision.
    """

    confirmation_id: str
    intent: TradeIntentDraft
    risk_decision: PreTradeRiskDecision
    idempotency_key: str
    created_at: datetime
    expires_at: datetime
    status: PaperConfirmationStatus = PaperConfirmationStatus.PENDING
    confirmed_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_text(self.confirmation_id, "confirmation_id")
        _require_text(self.idempotency_key, "idempotency_key")
        _require_aware_time(self.created_at, "created_at")
        _require_aware_time(self.expires_at, "expires_at")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at.")
        if self.risk_decision.intent_id != self.intent.intent_id:
            raise ValueError("risk_decision must belong to the confirmation intent.")
        if self.risk_decision.account_reference != self.intent.account_reference:
            raise ValueError("risk_decision must belong to the confirmation account.")
        if not self.risk_decision.is_approved:
            raise ValueError("paper confirmation requires an approved risk decision.")
        if self.status is PaperConfirmationStatus.PENDING:
            if self.confirmed_at is not None:
                raise ValueError("pending confirmation must not have confirmed_at.")
            return
        if self.status is PaperConfirmationStatus.CONFIRMED:
            if self.confirmed_at is None:
                raise ValueError("confirmed confirmation requires confirmed_at.")
            _require_aware_time(self.confirmed_at, "confirmed_at")
            if self.confirmed_at > self.expires_at:
                raise ValueError("confirmation cannot be confirmed after expiry.")
            return
        if self.status is PaperConfirmationStatus.EXPIRED:
            if self.confirmed_at is not None:
                raise ValueError("expired confirmation must not have confirmed_at.")
            return
        raise ValueError("status must be a PaperConfirmationStatus.")

    @property
    def owner_id(self) -> str:
        """Return the owner captured in the immutable intent snapshot."""
        return self.intent.owner_id

    def is_expired_at(self, now: datetime) -> bool:
        """Return whether a pending confirmation may no longer be used."""
        _require_aware_time(now, "now")
        return self.status is PaperConfirmationStatus.PENDING and now >= self.expires_at

    def mark_confirmed(self, confirmed_at: datetime) -> PaperTradeConfirmation:
        """Return a confirmed copy after successful second-factor verification."""
        _require_aware_time(confirmed_at, "confirmed_at")
        if self.status is not PaperConfirmationStatus.PENDING:
            raise ValueError("only a pending confirmation can be confirmed.")
        if confirmed_at >= self.expires_at:
            raise ValueError("expired confirmation cannot be confirmed.")
        return PaperTradeConfirmation(
            confirmation_id=self.confirmation_id,
            intent=self.intent,
            risk_decision=self.risk_decision,
            idempotency_key=self.idempotency_key,
            created_at=self.created_at,
            expires_at=self.expires_at,
            status=PaperConfirmationStatus.CONFIRMED,
            confirmed_at=confirmed_at,
        )

    def mark_expired(self, now: datetime) -> PaperTradeConfirmation:
        """Return a terminal expired copy without authorizing a submission."""
        _require_aware_time(now, "now")
        if self.status is not PaperConfirmationStatus.PENDING:
            return self
        if now < self.expires_at:
            raise ValueError("active confirmation cannot be expired early.")
        return PaperTradeConfirmation(
            confirmation_id=self.confirmation_id,
            intent=self.intent,
            risk_decision=self.risk_decision,
            idempotency_key=self.idempotency_key,
            created_at=self.created_at,
            expires_at=self.expires_at,
            status=PaperConfirmationStatus.EXPIRED,
        )


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty.")


def _require_aware_time(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
