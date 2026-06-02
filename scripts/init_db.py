"""Initialize database schema for local development.

Alembic remains the production migration mechanism. This script is convenient before migrations
contain business tables.
"""

from __future__ import annotations

import asyncio

from stocktrace.infrastructure.config import get_settings
from stocktrace.infrastructure.db import models as _models  # noqa: F401
from stocktrace.infrastructure.db.base import Base
from stocktrace.infrastructure.db.session import create_engine


async def main() -> None:
    """Create all currently registered tables."""
    settings = get_settings()
    engine = create_engine(settings.database)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
