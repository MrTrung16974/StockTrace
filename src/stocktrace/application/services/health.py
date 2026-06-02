"""Application-level health checks."""

from __future__ import annotations

from typing import Any


class HealthCheckService:
    """Expose health checks without binding routers to configuration internals."""

    def __init__(self, service_name: str, version: str, environment: str) -> None:
        self._service_name = service_name
        self._version = version
        self._environment = environment

    async def liveness(self) -> dict[str, Any]:
        """Return process liveness."""
        return self._base_payload(status="ok")

    async def readiness(self) -> dict[str, Any]:
        """Return readiness for dependencies introduced in this phase."""
        return self._base_payload(status="ok")

    def _base_payload(self, status: str) -> dict[str, Any]:
        return {
            "status": status,
            "service": self._service_name,
            "version": self._version,
            "environment": self._environment,
        }
