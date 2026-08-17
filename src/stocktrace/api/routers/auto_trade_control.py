"""Emergency stop endpoints for the paper-only auto-trade control plane."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from stocktrace.api.dependencies import (
    get_request_container,
    get_request_settings,
    require_auto_trade_control_key,
)
from stocktrace.api.schemas.auto_trade_control import (
    AutoTradeControlResponse,
    KillSwitchActivateRequest,
)
from stocktrace.application.services.auto_trade_control import AutoTradeControlService
from stocktrace.bootstrap.container import Container
from stocktrace.domain.entities.auto_trade_control import AutoTradeControlState
from stocktrace.infrastructure.config import Settings

router = APIRouter(prefix="/api/v1/system/auto-trade", tags=["auto-trade-control"])


def _control_service(container: Container) -> AutoTradeControlService:
    return container.auto_trade_control_service()


@router.get("/control", response_model=AutoTradeControlResponse)
async def get_control_state(
    container: Annotated[Container, Depends(get_request_container)],
    _: Annotated[None, Depends(require_auto_trade_control_key)],
) -> AutoTradeControlResponse:
    """Return the operational state without exposing control credentials."""
    return _response_from(await _control_service(container).get_state())


@router.post("/kill-switch/activate", response_model=AutoTradeControlResponse)
async def activate_kill_switch(
    payload: KillSwitchActivateRequest,
    container: Annotated[Container, Depends(get_request_container)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    _: Annotated[None, Depends(require_auto_trade_control_key)],
) -> AutoTradeControlResponse:
    """Stop all auto-trading immediately; this endpoint deliberately has no release action."""
    operator_id = settings.auto_trade.control_operator_id
    if not operator_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auto-trade control operator is not configured.",
        )
    state = await _control_service(container).activate_kill_switch(
        reason=payload.reason,
        authorized_operator_id=operator_id,
    )
    return _response_from(state)


def _response_from(state: AutoTradeControlState) -> AutoTradeControlResponse:
    """Convert the safe domain state without returning owner IDs or secrets."""
    return AutoTradeControlResponse(
        kill_switch_active=state.kill_switch_active,
        rollout_percentage=state.rollout_percentage,
        explicit_rollout_owner_count=len(state.rollout_owner_ids),
        updated_by=state.updated_by,
        updated_at=state.updated_at,
        kill_switch_reason=state.kill_switch_reason,
    )
