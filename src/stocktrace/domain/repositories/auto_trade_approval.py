"""Persistence contract for manual auto-trading pilot approvals."""

from __future__ import annotations

from typing import Protocol

from stocktrace.domain.entities.auto_trade import AutoTradeApprovalRecord


class AutoTradeApprovalRepository(Protocol):
    """Persist manual authority records outside configuration and Telegram."""

    async def save(self, approval: AutoTradeApprovalRecord) -> None:
        """Create or replace an approval record by opaque identifier."""

    async def get(self, approval_id: str) -> AutoTradeApprovalRecord | None:
        """Return a manual approval record by identifier."""

    async def get_active(
        self,
        *,
        owner_id: str,
        account_reference: str,
    ) -> AutoTradeApprovalRecord | None:
        """Return the current active approval for one pilot account, if present."""
