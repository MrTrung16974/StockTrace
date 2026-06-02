"""ASGI entrypoint for StockTrace."""

from __future__ import annotations

import uvicorn

from stocktrace.api.app import create_app
from stocktrace.infrastructure.config import get_settings

app = create_app()


def run() -> None:
    """Run the API server from the console script."""
    settings = get_settings()
    uvicorn.run(
        "stocktrace.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
