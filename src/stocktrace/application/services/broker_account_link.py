"""Secure application workflow for linking and unlinking a broker account."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import SecretStr

from stocktrace.domain.entities.broker_account_link import (
    BrokerAccountLink,
    BrokerAccountLinkStatus,
)
from stocktrace.domain.ports.secret_store import SecretStore
from stocktrace.domain.repositories.broker_account_link import BrokerAccountLinkRepository


class BrokerAccountLinkError(RuntimeError):
    """Base error for a safe broker account-link workflow."""


class BrokerAccountAlreadyLinkedError(BrokerAccountLinkError):
    """Raised when an active link already exists for the same broker account."""


class BrokerAccountLinkNotFoundError(BrokerAccountLinkError):
    """Raised when an unlink request references no broker account link."""


class BrokerAccountLinkService:
    """Link metadata to encrypted credential storage without exposing the credential."""

    def __init__(
        self,
        repository: BrokerAccountLinkRepository,
        secret_store: SecretStore,
    ) -> None:
        self._repository = repository
        self._secret_store = secret_store

    async def link(
        self,
        *,
        owner_id: str,
        broker_name: str,
        account_reference: str,
        credential: SecretStr,
        linked_at: datetime | None = None,
    ) -> BrokerAccountLink:
        """Encrypt a credential then persist only its opaque reference with the link."""
        timestamp = linked_at or datetime.now(UTC)
        _require_aware_time(timestamp, "linked_at")
        secret_value = credential.get_secret_value()
        if not secret_value.strip():
            raise ValueError("credential must not be empty.")
        active_link = await self._repository.get_active(
            owner_id=owner_id,
            broker_name=broker_name,
            account_reference=account_reference,
        )
        if active_link is not None:
            raise BrokerAccountAlreadyLinkedError("broker account is already linked.")

        link_id = str(uuid4())
        secret_reference = f"broker-credential:{uuid4()}"
        link = BrokerAccountLink(
            link_id=link_id,
            owner_id=owner_id,
            broker_name=broker_name,
            account_reference=account_reference,
            secret_reference=secret_reference,
            status=BrokerAccountLinkStatus.ACTIVE,
            linked_at=timestamp,
        )
        await self._secret_store.put(secret_reference, secret_value.encode("utf-8"))
        try:
            await self._repository.save(link)
        except Exception:
            await self._secret_store.revoke(secret_reference)
            raise
        return link

    async def unlink(
        self,
        link_id: str,
        *,
        revoked_at: datetime | None = None,
    ) -> BrokerAccountLink:
        """Revoke encrypted credentials before marking the metadata link inactive."""
        link = await self._repository.get(link_id)
        if link is None:
            raise BrokerAccountLinkNotFoundError("broker account link was not found.")
        if link.status is BrokerAccountLinkStatus.REVOKED:
            return link
        timestamp = revoked_at or datetime.now(UTC)
        _require_aware_time(timestamp, "revoked_at")
        await self._secret_store.revoke(link.secret_reference)
        revoked_link = link.revoke(timestamp)
        await self._repository.save(revoked_link)
        return revoked_link


def _require_aware_time(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
