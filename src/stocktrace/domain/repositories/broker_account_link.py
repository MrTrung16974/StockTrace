"""Persistence boundary for non-secret broker-account links."""

from __future__ import annotations

from typing import Protocol

from stocktrace.domain.entities.broker_account_link import BrokerAccountLink


class BrokerAccountLinkRepository(Protocol):
    """Store metadata only; credentials belong exclusively to SecretStore."""

    async def save(self, link: BrokerAccountLink) -> None:
        """Create or update a broker account link."""
        ...

    async def get(self, link_id: str) -> BrokerAccountLink | None:
        """Return a link by opaque identifier."""
        ...

    async def get_active(
        self,
        *,
        owner_id: str,
        broker_name: str,
        account_reference: str,
    ) -> BrokerAccountLink | None:
        """Return the current active link for one owner/broker/account tuple."""
        ...
