"""Small dependency container for application composition."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from stocktrace.application.services.health import HealthCheckService
from stocktrace.application.services.watchlist import WatchlistService
from stocktrace.domain.repositories.watchlist import WatchlistRepository
from stocktrace.infrastructure.config import Settings, get_settings
from stocktrace.infrastructure.db.repositories import SqlAlchemyWatchlistRepository
from stocktrace.infrastructure.db.session import SessionManager


class Container:
    """Composition root for use-case services.

    Later phases will add repository, provider, cache, notifier, and scheduler factories here.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session_manager = SessionManager(settings.database)

    def health_service(self) -> HealthCheckService:
        """Build the health service."""
        return HealthCheckService(
            service_name=self._settings.app.name,
            version=self._settings.app.version,
            environment=self._settings.environment.value,
        )

    def watchlist_service(self) -> WatchlistService:
        """Build the watchlist service."""
        return WatchlistService(repository_context_factory=self._watchlist_repository)

    async def dispose(self) -> None:
        """Dispose infrastructure resources."""
        await self._session_manager.dispose()

    @asynccontextmanager
    async def _watchlist_repository(self) -> AsyncIterator[WatchlistRepository]:
        async with self._session_manager.session() as session:
            yield SqlAlchemyWatchlistRepository(session=session)


@lru_cache(maxsize=1)
def get_container() -> Container:
    """Return the process-level dependency container."""
    return Container(settings=get_settings())
