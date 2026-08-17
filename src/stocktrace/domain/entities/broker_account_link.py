"""Non-secret broker-account link metadata."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum


class BrokerAccountLinkStatus(StrEnum):
    """Lifecycle state of an account link, independent of credential material."""

    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


@dataclass(frozen=True, slots=True)
class BrokerAccountLink:
    """A broker link that deliberately stores only a secret-store reference."""

    link_id: str
    owner_id: str
    broker_name: str
    account_reference: str
    secret_reference: str
    status: BrokerAccountLinkStatus
    linked_at: datetime
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.link_id, "link_id"),
            (self.owner_id, "owner_id"),
            (self.broker_name, "broker_name"),
            (self.account_reference, "account_reference"),
            (self.secret_reference, "secret_reference"),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} must not be empty.")
        _require_aware_time(self.linked_at, "linked_at")
        if self.status is BrokerAccountLinkStatus.ACTIVE and self.revoked_at is not None:
            raise ValueError("active link must not have revoked_at.")
        if self.status is BrokerAccountLinkStatus.REVOKED:
            if self.revoked_at is None:
                raise ValueError("revoked link requires revoked_at.")
            _require_aware_time(self.revoked_at, "revoked_at")

    def revoke(self, revoked_at: datetime) -> BrokerAccountLink:
        """Return a revoked copy; the credential itself is removed by SecretStore."""
        _require_aware_time(revoked_at, "revoked_at")
        if self.status is BrokerAccountLinkStatus.REVOKED:
            return self
        return replace(
            self,
            status=BrokerAccountLinkStatus.REVOKED,
            revoked_at=revoked_at,
        )


def _require_aware_time(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
