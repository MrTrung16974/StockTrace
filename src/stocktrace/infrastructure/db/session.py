"""Async SQLAlchemy engine and session manager."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from stocktrace.infrastructure.config import DatabaseSettings


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Create an async SQLAlchemy engine."""
    connect_args: dict[str, object] = {}
    engine_kwargs: dict[str, object] = {
        "echo": settings.echo,
    }
    if settings.is_sqlite:
        connect_args["check_same_thread"] = False
    else:
        engine_kwargs["pool_size"] = settings.pool_size
        engine_kwargs["max_overflow"] = settings.max_overflow

    return create_async_engine(settings.url, connect_args=connect_args, **engine_kwargs)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory."""
    return async_sessionmaker(engine, expire_on_commit=False)


class SessionManager:
    """Own database engine and session lifecycle."""

    def __init__(self, settings: DatabaseSettings) -> None:
        self._engine = create_engine(settings)
        self._session_factory = create_session_factory(self._engine)

    @property
    def engine(self) -> AsyncEngine:
        """Return the managed engine."""
        return self._engine

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Open a transactional async session."""
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def dispose(self) -> None:
        """Dispose engine connections."""
        await self._engine.dispose()
