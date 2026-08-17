"""Persistence boundary for global auto-trading operational controls."""

from __future__ import annotations

from typing import Protocol

from stocktrace.domain.entities.auto_trade_control import AutoTradeControlState


class AutoTradeControlRepository(Protocol):
    """Persist one globally authoritative, fail-closed control state."""

    async def get(self) -> AutoTradeControlState | None:
        """Return the current state, or none when the control plane is unavailable."""

    async def save(self, state: AutoTradeControlState) -> None:
        """Atomically replace current state with a newer audited snapshot."""
