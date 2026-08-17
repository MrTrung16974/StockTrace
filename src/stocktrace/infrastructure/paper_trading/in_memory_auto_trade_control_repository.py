"""Lock-protected runtime control state for development and paper-only tests."""

from __future__ import annotations

import asyncio

from stocktrace.domain.entities.auto_trade_control import AutoTradeControlState


class InMemoryAutoTradeControlRepository:
    """Transient adapter; use durable shared storage before any production pilot."""

    def __init__(self, initial_state: AutoTradeControlState | None = None) -> None:
        self._state = initial_state
        self._lock = asyncio.Lock()

    async def get(self) -> AutoTradeControlState | None:
        """Return the current atomic snapshot."""
        async with self._lock:
            return self._state

    async def save(self, state: AutoTradeControlState) -> None:
        """Replace state, preventing an older snapshot from overwriting a newer one."""
        async with self._lock:
            if self._state is not None and state.updated_at < self._state.updated_at:
                raise ValueError("cannot overwrite control state with an older update.")
            self._state = state
