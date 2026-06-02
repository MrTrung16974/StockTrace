"""Health check endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from stocktrace.api.dependencies import get_health_service
from stocktrace.api.schemas.health import HealthCheckResponse
from stocktrace.application.services.health import HealthCheckService

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthCheckResponse)
async def live(
    health_service: Annotated[HealthCheckService, Depends(get_health_service)],
) -> HealthCheckResponse:
    """Return process liveness."""
    result = await health_service.liveness()
    return HealthCheckResponse(**result)


@router.get("/ready", response_model=HealthCheckResponse)
async def ready(
    health_service: Annotated[HealthCheckService, Depends(get_health_service)],
) -> HealthCheckResponse:
    """Return dependency readiness."""
    result = await health_service.readiness()
    return HealthCheckResponse(**result)
