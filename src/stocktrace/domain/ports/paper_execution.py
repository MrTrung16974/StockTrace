"""Port for deterministic, paper-only execution simulation."""

from __future__ import annotations

from typing import Protocol

from stocktrace.domain.entities.paper_trading import (
    PaperAccountSnapshot,
)
from stocktrace.domain.ports.broker_execution import BrokerExecutionPort


class PaperExecutionPort(BrokerExecutionPort, Protocol):
    """Simulate execution only; this protocol has no real broker capability."""

    async def register_account(self, account: PaperAccountSnapshot) -> None:
        """Register a local paper account with initial cash and positions."""
        ...

    async def get_account(self, account_reference: str) -> PaperAccountSnapshot | None:
        """Return the latest simulated account state."""
        ...
