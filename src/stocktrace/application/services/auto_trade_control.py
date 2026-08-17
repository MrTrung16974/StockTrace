"""Operational control plane for immediate auto-trading shutdown."""

from __future__ import annotations

from datetime import UTC, datetime

from stocktrace.domain.entities.auto_trade_control import AutoTradeControlState
from stocktrace.domain.ports.trade_pipeline_observer import TradePipelineObserver
from stocktrace.domain.repositories.auto_trade_control import AutoTradeControlRepository


class AutoTradeControlService:
    """Read and activate a global kill switch; this service never submits orders."""

    def __init__(
        self,
        repository: AutoTradeControlRepository,
        *,
        observer: TradePipelineObserver | None = None,
    ) -> None:
        self._repository = repository
        self._observer = observer

    async def get_state(self, *, now: datetime | None = None) -> AutoTradeControlState:
        """Return current control state, defaulting safely to an active kill switch."""
        state = await self._repository.get()
        if state is not None:
            return state
        timestamp = now or datetime.now(UTC)
        return AutoTradeControlState.initially_killed(
            updated_by="system-uninitialized-control-plane",
            updated_at=timestamp,
        )

    async def activate_kill_switch(
        self,
        *,
        reason: str,
        authorized_operator_id: str,
        activated_at: datetime | None = None,
    ) -> AutoTradeControlState:
        """Stop all auto-trading immediately and persist the latest stop reason."""
        timestamp = activated_at or datetime.now(UTC)
        state = await self.get_state(now=timestamp)
        stopped = state.activate_kill_switch(
            reason=reason,
            updated_by=authorized_operator_id,
            updated_at=timestamp,
        )
        await self._repository.save(stopped)
        if self._observer is not None:
            self._observer.record_kill_switch(stopped)
        return stopped
