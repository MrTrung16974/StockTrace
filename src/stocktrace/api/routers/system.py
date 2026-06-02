"""System status endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from stocktrace.api.dependencies import get_request_settings
from stocktrace.api.schemas.system import SystemStatusResponse
from stocktrace.infrastructure.config import Settings

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status", response_model=SystemStatusResponse)
async def status(
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> SystemStatusResponse:
    """Return basic runtime and feature status."""
    return SystemStatusResponse(
        service=settings.app.name,
        version=settings.app.version,
        environment=settings.environment.value,
        debug=settings.debug,
        database_backend="sqlite" if settings.database.is_sqlite else "postgresql",
        redis_enabled=settings.redis.enabled,
        telegram_configured=settings.telegram.bot_token is not None,
    )
