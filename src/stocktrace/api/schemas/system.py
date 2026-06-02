"""System status schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SystemStatusResponse(BaseModel):
    """Runtime status exposed to authenticated API clients."""

    service: str = Field(examples=["StockTrace"])
    version: str = Field(examples=["0.1.0"])
    environment: str = Field(examples=["development"])
    debug: bool
    database_backend: str = Field(examples=["postgresql"])
    redis_enabled: bool
    telegram_configured: bool
