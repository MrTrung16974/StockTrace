"""Fail-closed placeholder for a future officially approved broker adapter."""

from __future__ import annotations

from datetime import datetime
from typing import NoReturn

from stocktrace.domain.entities.investment_suggestion import TradeIntentDraft
from stocktrace.domain.entities.paper_trading import (
    PaperAccountSnapshot,
    PaperExecutionReceipt,
    PaperTradeApproval,
)
from stocktrace.domain.ports.broker_execution import BrokerIntegrationNotConfiguredError


class OfficialBrokerSkeleton:
    """Contract-shaped adapter that has no endpoint, credentials, or network access."""

    def __init__(self, broker_name: str) -> None:
        if not broker_name.strip():
            raise ValueError("broker_name must not be empty.")
        self._broker_name = broker_name

    @property
    def broker_name(self) -> str:
        """Return the candidate broker identifier without claiming integration support."""
        return self._broker_name

    async def get_account(self, account_reference: str) -> PaperAccountSnapshot | None:
        """Fail closed because no official broker account adapter is configured."""
        del account_reference
        self._raise_not_configured()

    async def submit_order(
        self,
        intent: TradeIntentDraft,
        approval: PaperTradeApproval,
        *,
        submitted_at: datetime,
    ) -> PaperExecutionReceipt:
        """Fail closed; a skeleton can never submit a real order."""
        del intent, approval, submitted_at
        self._raise_not_configured()

    async def cancel_order(
        self,
        order_id: str,
        *,
        requested_at: datetime,
    ) -> PaperExecutionReceipt:
        """Fail closed; cancellation needs the selected broker's official API."""
        del order_id, requested_at
        self._raise_not_configured()

    async def get_order(self, order_id: str) -> PaperExecutionReceipt | None:
        """Fail closed; no order-state API is configured."""
        del order_id
        self._raise_not_configured()

    async def get_fills(self, order_id: str) -> tuple[PaperExecutionReceipt, ...]:
        """Fail closed; no fill-query API is configured."""
        del order_id
        self._raise_not_configured()

    def _raise_not_configured(self) -> NoReturn:
        raise BrokerIntegrationNotConfiguredError(
            "Official broker integration is blocked until ADR Phase 1 is accepted "
            "and the broker's official API contract is verified.",
        )
