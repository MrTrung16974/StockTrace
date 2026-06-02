"""FastAPI dependency helpers."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request

from stocktrace.application.services.health import HealthCheckService
from stocktrace.bootstrap.container import Container
from stocktrace.infrastructure.config import Settings


def get_request_settings(request: Request) -> Settings:
    """Return settings attached to the current app."""
    return cast(Settings, request.app.state.settings)


def get_request_container(request: Request) -> Container:
    """Return the per-app dependency container."""
    return cast(Container, request.app.state.container)


def get_health_service(
    container: Annotated[Container, Depends(get_request_container)],
) -> HealthCheckService:
    """Return the health service from the application container."""
    return container.health_service()
