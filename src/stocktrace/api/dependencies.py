"""FastAPI dependency helpers."""

from __future__ import annotations

from hmac import compare_digest
from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status

from stocktrace.application.services.health import HealthCheckService
from stocktrace.bootstrap.container import Container
from stocktrace.infrastructure.config import Settings


def get_request_settings(request: Request) -> Settings:
    """Return settings attached to the current app."""
    return cast(Settings, request.app.state.settings)


def get_request_container(request: Request) -> Container:
    """Return the per-app dependency container."""
    return cast(Container, request.app.state.container)


def require_auto_trade_control_key(request: Request) -> None:
    """Require a dedicated operator key in addition to global API-key middleware."""
    settings = get_request_settings(request)
    configured_key = settings.auto_trade.control_key
    if configured_key is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auto-trade control endpoint is not configured.",
        )
    provided_key = request.headers.get(settings.auto_trade.control_key_header)
    if provided_key is None or not compare_digest(provided_key, configured_key.get_secret_value()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid auto-trade control key.",
        )


def get_health_service(
    container: Annotated[Container, Depends(get_request_container)],
) -> HealthCheckService:
    """Return the health service from the application container."""
    return container.health_service()
