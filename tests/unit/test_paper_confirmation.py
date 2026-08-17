"""Tests for Phase-13 secure paper-confirmation safeguards."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from cryptography.fernet import Fernet

from stocktrace.application.services.paper_confirmation import (
    PaperConfirmationExpiredError,
    PaperConfirmationOwnershipError,
    PaperConfirmationService,
    PaperSecondFactorInvalidError,
)
from stocktrace.domain.entities.investment_suggestion import (
    SuggestionAction,
    TradeIntentDraft,
    TradeSide,
)
from stocktrace.domain.entities.paper_confirmation import PaperConfirmationStatus
from stocktrace.domain.entities.paper_trading import PaperAccountSnapshot
from stocktrace.domain.entities.pre_trade_risk import PreTradeRiskDecision, RiskPolicy
from stocktrace.domain.services.pre_trade_risk import PreTradeRiskEngine
from stocktrace.infrastructure.paper_trading.in_memory_confirmation_repository import (
    InMemoryPaperConfirmationRepository,
)
from stocktrace.infrastructure.scheduler.paper_confirmation_expiry_job import (
    PaperConfirmationExpiryJob,
)
from stocktrace.infrastructure.security.encrypted_memory_secret_store import (
    EncryptedInMemorySecretStore,
)
from stocktrace.infrastructure.security.totp_second_factor import (
    TotpSecondFactorVerifier,
    _totp_code,
)

NOW = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
OWNER_ID = "owner-1"
TOTP_SECRET = b"JBSWY3DPEHPK3PXP"


def _intent() -> TradeIntentDraft:
    return TradeIntentDraft(
        owner_id=OWNER_ID,
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


def _approved_decision(intent: TradeIntentDraft) -> PreTradeRiskDecision:
    return PreTradeRiskEngine().assess(
        intent,
        PaperAccountSnapshot("paper-1", OWNER_ID, Decimal("3000000")),
        orders_submitted_today=0,
        policy=RiskPolicy(100, Decimal("3000000"), 2, "risk-v1"),
        checked_at=NOW,
    )


async def _configured_service(
    *, confirmation_ttl: timedelta = timedelta(minutes=5)
) -> tuple[PaperConfirmationService, InMemoryPaperConfirmationRepository]:
    store = EncryptedInMemorySecretStore(Fernet.generate_key())
    await store.put(f"paper-confirmation-totp:{OWNER_ID}", TOTP_SECRET)
    repository = InMemoryPaperConfirmationRepository()
    return (
        PaperConfirmationService(
            repository,
            TotpSecondFactorVerifier(store, valid_window=0),
            confirmation_ttl=confirmation_ttl,
        ),
        repository,
    )


@pytest.mark.asyncio
async def test_confirmed_paper_order_requires_owner_totp_and_is_idempotent() -> None:
    service, repository = await _configured_service()
    intent = _intent()
    confirmation = await service.create(intent, _approved_decision(intent), created_at=NOW)
    code = _totp_code(
        base64.b32decode(TOTP_SECRET),
        int(NOW.timestamp()) // 30,
        6,
    )

    approval = await service.confirm(
        confirmation.confirmation_id,
        authenticated_owner_id=OWNER_ID,
        second_factor_code=code,
        confirmed_at=NOW,
    )
    retried_approval = await service.confirm(
        confirmation.confirmation_id,
        authenticated_owner_id=OWNER_ID,
        second_factor_code="000000",
        confirmed_at=NOW,
    )

    stored = await repository.get(confirmation.confirmation_id)
    assert approval.idempotency_key == confirmation.idempotency_key
    assert retried_approval == approval
    assert stored is not None
    assert stored.status is PaperConfirmationStatus.CONFIRMED


@pytest.mark.asyncio
async def test_confirmation_rejects_wrong_owner_and_invalid_or_replayed_totp() -> None:
    service, _ = await _configured_service()
    intent = _intent()
    confirmation = await service.create(intent, _approved_decision(intent), created_at=NOW)
    code = _totp_code(
        base64.b32decode(TOTP_SECRET),
        int(NOW.timestamp()) // 30,
        6,
    )

    with pytest.raises(PaperConfirmationOwnershipError):
        await service.confirm(
            confirmation.confirmation_id,
            authenticated_owner_id="other-owner",
            second_factor_code=code,
            confirmed_at=NOW,
        )
    with pytest.raises(PaperSecondFactorInvalidError):
        await service.confirm(
            confirmation.confirmation_id,
            authenticated_owner_id=OWNER_ID,
            second_factor_code="000000",
            confirmed_at=NOW,
        )


@pytest.mark.asyncio
async def test_expiry_job_terminally_cancels_pending_confirmation() -> None:
    service, repository = await _configured_service(confirmation_ttl=timedelta(minutes=1))
    intent = _intent()
    confirmation = await service.create(intent, _approved_decision(intent), created_at=NOW)

    expired_count = await service.expire_due(now=NOW + timedelta(minutes=1))
    stored = await repository.get(confirmation.confirmation_id)

    assert expired_count == 1
    assert stored is not None
    assert stored.status is PaperConfirmationStatus.EXPIRED
    with pytest.raises(PaperConfirmationExpiredError):
        await service.confirm(
            confirmation.confirmation_id,
            authenticated_owner_id=OWNER_ID,
            second_factor_code=_totp_code(
                base64.b32decode(TOTP_SECRET),
                int(NOW.timestamp()) // 30,
                6,
            ),
            confirmed_at=NOW + timedelta(minutes=1),
        )


@pytest.mark.asyncio
async def test_expiry_job_delegates_only_to_expiry_service() -> None:
    class FakeConfirmationService:
        calls = 0

        async def expire_due(self) -> int:
            self.calls += 1
            return 2

    service = FakeConfirmationService()
    job = PaperConfirmationExpiryJob(service)  # type: ignore[arg-type]
    await job.run()

    assert service.calls == 1
