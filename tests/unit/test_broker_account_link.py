"""Tests for encrypted credentials and metadata-only broker account links."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from stocktrace.application.services.broker_account_link import (
    BrokerAccountAlreadyLinkedError,
    BrokerAccountLinkService,
)
from stocktrace.domain.entities.broker_account_link import BrokerAccountLinkStatus
from stocktrace.infrastructure.security.encrypted_memory_secret_store import (
    EncryptedInMemorySecretStore,
)
from stocktrace.infrastructure.security.in_memory_broker_account_link_repository import (
    InMemoryBrokerAccountLinkRepository,
)

NOW = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
_CREDENTIAL = "test-broker-token"


def _service() -> tuple[BrokerAccountLinkService, EncryptedInMemorySecretStore]:
    store = EncryptedInMemorySecretStore(Fernet.generate_key())
    return BrokerAccountLinkService(InMemoryBrokerAccountLinkRepository(), store), store


@pytest.mark.asyncio
async def test_link_stores_only_an_opaque_reference_and_encrypts_credential() -> None:
    service, store = _service()

    link = await service.link(
        owner_id="owner-1",
        broker_name="candidate-broker",
        account_reference="account-1",
        credential=SecretStr(_CREDENTIAL),
        linked_at=NOW,
    )

    assert link.status is BrokerAccountLinkStatus.ACTIVE
    assert _CREDENTIAL not in repr(link)
    assert store._ciphertexts[link.secret_reference] != _CREDENTIAL.encode("utf-8")
    assert await store.get(link.secret_reference) == _CREDENTIAL.encode("utf-8")


@pytest.mark.asyncio
async def test_unlink_revokes_credential_before_metadata_is_returned_as_inactive() -> None:
    service, store = _service()
    link = await service.link(
        owner_id="owner-1",
        broker_name="candidate-broker",
        account_reference="account-1",
        credential=SecretStr(_CREDENTIAL),
        linked_at=NOW,
    )

    revoked = await service.unlink(link.link_id, revoked_at=NOW)

    assert revoked.status is BrokerAccountLinkStatus.REVOKED
    assert await store.get(link.secret_reference) is None


@pytest.mark.asyncio
async def test_link_rejects_a_duplicate_active_account_without_overwriting_secret() -> None:
    service, _ = _service()
    await service.link(
        owner_id="owner-1",
        broker_name="candidate-broker",
        account_reference="account-1",
        credential=SecretStr(_CREDENTIAL),
        linked_at=NOW,
    )

    with pytest.raises(BrokerAccountAlreadyLinkedError):
        await service.link(
            owner_id="owner-1",
            broker_name="candidate-broker",
            account_reference="account-1",
            credential=SecretStr("different-token"),
            linked_at=NOW,
        )
