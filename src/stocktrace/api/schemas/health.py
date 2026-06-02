"""Health response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthCheckResponse(BaseModel):
    """Public health check response."""

    status: str = Field(examples=["ok"])
    service: str = Field(examples=["StockTrace"])
    version: str = Field(examples=["0.1.0"])
    environment: str = Field(examples=["development"])
