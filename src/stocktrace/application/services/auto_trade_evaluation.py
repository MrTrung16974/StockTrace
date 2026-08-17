"""Application orchestration that combines pilot limits with operational controls."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from stocktrace.domain.entities.auto_trade import (
    AutoTradeApprovalRecord,
    AutoTradeGateDecision,
    AutoTradePilotPolicy,
)
from stocktrace.domain.entities.investment_suggestion import TradeIntentDraft
from stocktrace.domain.entities.pre_trade_risk import PreTradeRiskDecision
from stocktrace.domain.ports.trade_pipeline_observer import TradePipelineObserver
from stocktrace.domain.repositories.auto_trade_control import AutoTradeControlRepository
from stocktrace.domain.services.auto_trade_gate import AutoTradeGate


class AutoTradeEvaluationService:
    """Evaluate auto-trading against dynamic control state before any submit path."""

    def __init__(
        self,
        control_repository: AutoTradeControlRepository,
        *,
        observer: TradePipelineObserver | None = None,
    ) -> None:
        self._control_repository = control_repository
        self._observer = observer
        self._gate = AutoTradeGate()

    async def assess(
        self,
        intent: TradeIntentDraft,
        risk_decision: PreTradeRiskDecision,
        approval: AutoTradeApprovalRecord | None,
        policy: AutoTradePilotPolicy,
        *,
        orders_submitted_today: int,
        notional_submitted_today: Decimal,
        checked_at: datetime,
    ) -> AutoTradeGateDecision:
        """Read controls at execution time so a kill switch takes effect immediately."""
        control_state = await self._control_repository.get()
        decision = self._gate.assess(
            intent,
            risk_decision,
            approval,
            policy,
            control_state=control_state,
            orders_submitted_today=orders_submitted_today,
            notional_submitted_today=notional_submitted_today,
            checked_at=checked_at,
        )
        if self._observer is not None:
            self._observer.record_auto_trade_gate(decision, control_state)
        return decision
