"""Prometheus implementation of the safety-critical trade pipeline observer."""

from __future__ import annotations

from stocktrace.domain.entities.auto_trade import AutoTradeGateDecision
from stocktrace.domain.entities.auto_trade_control import AutoTradeControlState
from stocktrace.infrastructure.metrics.prometheus import (
    auto_trade_gate_decisions_total,
    auto_trade_kill_switch_active,
    auto_trade_rollout_percentage,
)


class PrometheusTradePipelineObserver:
    """Best-effort metrics observer that can never authorize a trade."""

    def record_auto_trade_gate(
        self,
        decision: AutoTradeGateDecision,
        control_state: AutoTradeControlState | None,
    ) -> None:
        """Record a decision and refresh safe dynamic-control gauges."""
        outcome = "authorized" if decision.is_authorized else "blocked"
        block_code = "NONE" if decision.is_authorized else decision.blocks[0].value
        auto_trade_gate_decisions_total.labels(outcome=outcome, block_code=block_code).inc()
        if control_state is not None:
            self.record_kill_switch(control_state)

    def record_kill_switch(self, state: AutoTradeControlState) -> None:
        """Set current stop state and rollout percentage."""
        auto_trade_kill_switch_active.set(1 if state.kill_switch_active else 0)
        auto_trade_rollout_percentage.set(state.rollout_percentage)
