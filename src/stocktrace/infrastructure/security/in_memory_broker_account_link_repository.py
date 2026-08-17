"""Transient metadata repository for local broker-link workflow testing."""

from __future__ import annotations

from stocktrace.domain.entities.broker_account_link import (
    BrokerAccountLink,
    BrokerAccountLinkStatus,
)


class InMemoryBrokerAccountLinkRepository:
    """Hold non-secret links in memory; production needs a reviewed persistence adapter."""

    def __init__(self) -> None:
        self._links: dict[str, BrokerAccountLink] = {}

    async def save(self, link: BrokerAccountLink) -> None:
        """Store non-secret link metadata."""
        self._links[link.link_id] = link

    async def get(self, link_id: str) -> BrokerAccountLink | None:
        """Return one metadata-only link."""
        return self._links.get(link_id)

    async def get_active(
        self,
        *,
        owner_id: str,
        broker_name: str,
        account_reference: str,
    ) -> BrokerAccountLink | None:
        """Find an exact active owner/broker/account link."""
        for link in self._links.values():
            if (
                link.status is BrokerAccountLinkStatus.ACTIVE
                and link.owner_id == owner_id
                and link.broker_name == broker_name
                and link.account_reference == account_reference
            ):
                return link
        return None
