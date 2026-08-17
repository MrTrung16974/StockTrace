"""Common broker-execution boundary shared by paper and future official adapters."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from stocktrace.domain.entities.investment_suggestion import TradeIntentDraft
from stocktrace.domain.entities.paper_trading import (
    PaperAccountSnapshot,
    PaperExecutionReceipt,
    PaperTradeApproval,
)


class BrokerExecutionError(RuntimeError):
    """Base error for an execution adapter; callers must never infer a fill from it."""


class BrokerIntegrationNotConfiguredError(BrokerExecutionError):
    """Raised by the real-broker skeleton until official integration is approved."""


class BrokerOrderNotFoundError(BrokerExecutionError):
    """Raised when an adapter cannot locate an order identifier."""


class BrokerOrderNotCancellableError(BrokerExecutionError):
    """Raised when an order has already reached a terminal state."""


class BrokerExecutionPort(Protocol):
    """Execution boundary; implementations must report, never invent, order state."""

    @property
    def broker_name(self) -> str:
        """Return a stable adapter identifier for audit and diagnostics."""
        ...

    async def get_account(self, account_reference: str) -> PaperAccountSnapshot | None:
        """Return the adapter account state when it is available."""
        ...

    async def submit_order(
        self,
        intent: TradeIntentDraft,
        approval: PaperTradeApproval,
        *,
        submitted_at: datetime,
    ) -> PaperExecutionReceipt:
        """Submit an already-authorized limit order and return its explicit outcome."""
        ...

    async def cancel_order(
        self,
        order_id: str,
        *,
        requested_at: datetime,
    ) -> PaperExecutionReceipt:
        """Cancel a non-terminal order or raise an explicit adapter error."""
        ...

    async def get_order(self, order_id: str) -> PaperExecutionReceipt | None:
        """Query the adapter's explicit state for one order."""
        ...

    async def get_fills(self, order_id: str) -> tuple[PaperExecutionReceipt, ...]:
        """Return confirmed fills for one order; no result means no confirmed fill."""
        ...
