"""Safe request/response contracts for emergency auto-trade controls."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class KillSwitchActivateRequest(BaseModel):
    """Reason retained in the control-state audit record."""

    reason: str = Field(min_length=3, max_length=500)


class AutoTradeControlResponse(BaseModel):
    """Non-secret runtime state exposed only to authenticated operators."""

    kill_switch_active: bool
    rollout_percentage: int
    explicit_rollout_owner_count: int
    updated_by: str
    updated_at: datetime
    kill_switch_reason: str | None
