"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from stocktrace.api.middleware.request_timing import RequestTimingMiddleware
from stocktrace.api.middleware.security import ApiSecurityMiddleware
from stocktrace.api.routers import health, stocks, system
from stocktrace.bootstrap.container import Container
from stocktrace.infrastructure.config import Settings, get_settings
from stocktrace.infrastructure.logging.config import configure_logging, get_logger
from stocktrace.infrastructure.telegram.runner import TelegramBotRunner


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle."""
    settings = app.state.settings if hasattr(app.state, "settings") else get_settings()
    configure_logging(settings.logging)
    logger = get_logger(__name__)
    logger.info("application_starting", environment=settings.environment)
    app.state.settings = settings
    container = (
        app.state.container
        if hasattr(app.state, "container")
        else Container(settings=settings)
    )
    app.state.container = container
    app.state.telegram_runner = TelegramBotRunner(
        settings=settings,
        watchlist_service=container.watchlist_service(),
        market_data_service=container.market_data_service(),
        stock_analysis_service=container.stock_analysis_service(),
        scheduler_service_factory=container.scheduler_service,
    )
    await app.state.telegram_runner.start()
    yield
    await app.state.telegram_runner.stop()
    await container.dispose()
    logger.info("application_stopping", environment=settings.environment)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create a configured FastAPI application."""
    app_settings = settings or get_settings()
    configure_logging(app_settings.logging)

    app = FastAPI(
        title=app_settings.app.name,
        version=app_settings.app.version,
        debug=app_settings.debug,
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.container = Container(settings=app_settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(ApiSecurityMiddleware, settings=app_settings.security)
    app.add_middleware(RequestTimingMiddleware)

    app.include_router(health.router)
    app.include_router(system.router)
    app.include_router(stocks.router)
    return app
