"""Observability boundary for the safety-critical order pipeline."""

from __future__ import annotations

from typing import Protocol

from stocktrace.domain.entities.auto_trade import AutoTradeGateDecision
from stocktrace.domain.entities.auto_trade_control import AutoTradeControlState


class TradePipelineObserver(Protocol):
    """Record non-sensitive pipeline outcomes without influencing a decision."""

    def record_auto_trade_gate(
        self,
        decision: AutoTradeGateDecision,
        control_state: AutoTradeControlState | None,
    ) -> None:
        """Record one gate authorization or explicit block reason."""

    def record_kill_switch(self, state: AutoTradeControlState) -> None:
        """Record active kill-switch and rollout gauge values."""
