"""Secure paper-order confirmation orchestration, intentionally UI-agnostic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from stocktrace.domain.entities.investment_suggestion import TradeIntentDraft
from stocktrace.domain.entities.paper_confirmation import (
    PaperConfirmationStatus,
    PaperTradeConfirmation,
)
from stocktrace.domain.entities.paper_trading import PaperTradeApproval
from stocktrace.domain.entities.pre_trade_risk import PreTradeRiskDecision
from stocktrace.domain.ports.second_factor import SecondFactorVerifier
from stocktrace.domain.repositories.paper_confirmation import PaperConfirmationRepository


class PaperConfirmationError(RuntimeError):
    """Base error that is safe for the trusted web-confirmation boundary."""


class PaperConfirmationNotFoundError(PaperConfirmationError):
    """Raised when the confirmation identifier is unknown."""


class PaperConfirmationOwnershipError(PaperConfirmationError):
    """Raised when a different authenticated owner tries to confirm an intent."""


class PaperConfirmationExpiredError(PaperConfirmationError):
    """Raised when a confirmation is expired and was never authorized."""


class PaperSecondFactorInvalidError(PaperConfirmationError):
    """Raised when a submitted second factor is invalid or replayed."""


class PaperConfirmationService:
    """Create, confirm, and expire paper-only orders without submitting them."""

    def __init__(
        self,
        repository: PaperConfirmationRepository,
        second_factor_verifier: SecondFactorVerifier,
        *,
        confirmation_ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        if confirmation_ttl <= timedelta(0):
            raise ValueError("confirmation_ttl must be greater than zero.")
        self._repository = repository
        self._second_factor_verifier = second_factor_verifier
        self._confirmation_ttl = confirmation_ttl

    async def create(
        self,
        intent: TradeIntentDraft,
        risk_decision: PreTradeRiskDecision,
        *,
        created_at: datetime | None = None,
    ) -> PaperTradeConfirmation:
        """Persist an exact risk-approved snapshot for the trusted confirmation UI."""
        timestamp = created_at or datetime.now(UTC)
        _require_aware_time(timestamp)
        confirmation = PaperTradeConfirmation(
            confirmation_id=str(uuid4()),
            intent=intent,
            risk_decision=risk_decision,
            idempotency_key=str(uuid4()),
            created_at=timestamp,
            expires_at=timestamp + self._confirmation_ttl,
        )
        await self._repository.save(confirmation)
        return confirmation

    async def confirm(
        self,
        confirmation_id: str,
        *,
        authenticated_owner_id: str,
        second_factor_code: str,
        confirmed_at: datetime | None = None,
    ) -> PaperTradeApproval:
        """Verify owner + TOTP, then issue a single paper-only approval token."""
        if not authenticated_owner_id.strip():
            raise ValueError("authenticated_owner_id must not be empty.")
        timestamp = confirmed_at or datetime.now(UTC)
        _require_aware_time(timestamp)
        confirmation = await self._get_required(confirmation_id)
        if confirmation.owner_id != authenticated_owner_id:
            raise PaperConfirmationOwnershipError("confirmation does not belong to this owner.")
        if (
            confirmation.status is PaperConfirmationStatus.EXPIRED
            or confirmation.is_expired_at(timestamp)
        ):
            if confirmation.status is PaperConfirmationStatus.PENDING:
                await self._repository.save(confirmation.mark_expired(timestamp))
            raise PaperConfirmationExpiredError("confirmation has expired.")
        if confirmation.status is PaperConfirmationStatus.CONFIRMED:
            return _approval_from(confirmation)
        if not await self._second_factor_verifier.verify(
            authenticated_owner_id,
            second_factor_code,
            verified_at=timestamp,
        ):
            raise PaperSecondFactorInvalidError(
                "second factor is invalid or has already been used.",
            )
        confirmed = confirmation.mark_confirmed(timestamp)
        await self._repository.save(confirmed)
        return _approval_from(confirmed)

    async def expire_due(self, *, now: datetime | None = None) -> int:
        """Terminally expire outstanding confirmations; never submit an order."""
        timestamp = now or datetime.now(UTC)
        _require_aware_time(timestamp)
        expired = await self._repository.list_expired_pending(now=timestamp)
        for confirmation in expired:
            await self._repository.save(confirmation.mark_expired(timestamp))
        return len(expired)

    async def _get_required(self, confirmation_id: str) -> PaperTradeConfirmation:
        if not confirmation_id.strip():
            raise ValueError("confirmation_id must not be empty.")
        confirmation = await self._repository.get(confirmation_id)
        if confirmation is None:
            raise PaperConfirmationNotFoundError("confirmation was not found.")
        return confirmation


def _approval_from(confirmation: PaperTradeConfirmation) -> PaperTradeApproval:
    if confirmation.status is not PaperConfirmationStatus.CONFIRMED:
        raise ValueError("only confirmed records can issue an approval.")
    if confirmation.confirmed_at is None:
        raise ValueError("confirmed record unexpectedly lacks confirmed_at.")
    return PaperTradeApproval(
        intent_id=confirmation.intent.intent_id,
        risk_decision=confirmation.risk_decision,
        two_factor_verified=True,
        confirmation_expires_at=confirmation.expires_at,
        idempotency_key=confirmation.idempotency_key,
        verified_at=confirmation.confirmed_at,
    )


def _require_aware_time(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware.")
