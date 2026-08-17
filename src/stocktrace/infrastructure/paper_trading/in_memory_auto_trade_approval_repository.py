"""Transient manual-approval store for a paper-only auto-trading pilot."""

from __future__ import annotations

import asyncio

from stocktrace.domain.entities.auto_trade import (
    AutoTradeApprovalRecord,
    AutoTradeApprovalStatus,
)


class InMemoryAutoTradeApprovalRepository:
    """Concurrency-safe test/development repository; never use for real authority."""

    def __init__(self) -> None:
        self._approvals: dict[str, AutoTradeApprovalRecord] = {}
        self._lock = asyncio.Lock()

    async def save(self, approval: AutoTradeApprovalRecord) -> None:
        """Store the immutable approval state by opaque identifier."""
        async with self._lock:
            self._approvals[approval.approval_id] = approval

    async def get(self, approval_id: str) -> AutoTradeApprovalRecord | None:
        """Return one approval record by identifier."""
        async with self._lock:
            return self._approvals.get(approval_id)

    async def get_active(
        self,
        *,
        owner_id: str,
        account_reference: str,
    ) -> AutoTradeApprovalRecord | None:
        """Return the sole active approval record for one owner/account pair."""
        async with self._lock:
            return next(
                (
                    approval
                    for approval in self._approvals.values()
                    if approval.owner_id == owner_id
                    and approval.account_reference == account_reference
                    and approval.status is AutoTradeApprovalStatus.ACTIVE
                ),
                None,
            )
