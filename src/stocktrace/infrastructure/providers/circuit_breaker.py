"""Async circuit breaker implementation for external providers."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from enum import StrEnum

from stocktrace.infrastructure.logging.config import get_logger


class CircuitState(StrEnum):
    """Circuit breaker states."""

    CLOSED = "CLOSED"       # Normal operation — requests pass through
    OPEN = "OPEN"           # Failing — requests are rejected immediately
    HALF_OPEN = "HALF_OPEN" # Recovery probe — one request allowed through


class CircuitBreakerOpenError(RuntimeError):
    """Raised when a request is rejected because the circuit is OPEN."""


class CircuitBreaker:
    """Per-provider circuit breaker with CLOSED → OPEN → HALF_OPEN → CLOSED lifecycle.

    State transitions:
        CLOSED  → OPEN      : ``failure_threshold`` consecutive failures
        OPEN    → HALF_OPEN : ``recovery_timeout`` seconds elapsed
        HALF_OPEN → CLOSED  : next request succeeds
        HALF_OPEN → OPEN    : next request fails
    """

    def __init__(
        self,
        provider_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> None:
        self._name = provider_name
        self._threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at: datetime | None = None
        self._lock = asyncio.Lock()
        self._logger = get_logger(__name__)

    @property
    def state(self) -> CircuitState:
        """Return current circuit state."""
        return self._state

    @property
    def name(self) -> str:
        """Return the provider name this circuit guards."""
        return self._name

    async def call(self, coro: object) -> object:
        """Execute *coro* if the circuit allows; raise CircuitBreakerOpenError otherwise."""
        import asyncio as _asyncio  # noqa: PLC0415

        async with self._lock:
            await self._maybe_transition_to_half_open()
            if self._state == CircuitState.OPEN:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker OPEN for provider '{self._name}'. "
                    f"Will retry after {self._recovery_timeout}s."
                )

        try:
            result = await coro  # type: ignore[misc]
            await self._on_success()
            return result
        except Exception:
            await self._on_failure()
            raise

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    async def _on_success(self) -> None:
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._logger.info("circuit_breaker_closed", provider=self._name)
                self._state = CircuitState.CLOSED
            self._failures = 0
            self._opened_at = None
            self._update_gauge()

    async def _on_failure(self) -> None:
        async with self._lock:
            self._failures += 1
            if self._state == CircuitState.HALF_OPEN or self._failures >= self._threshold:
                self._trip()

    def _trip(self) -> None:
        """Transition to OPEN (called while holding _lock)."""
        if self._state != CircuitState.OPEN:
            self._logger.warning(
                "circuit_breaker_opened",
                provider=self._name,
                failures=self._failures,
            )
            self._state = CircuitState.OPEN
            self._opened_at = datetime.now(UTC)
            self._update_gauge()
            self._emit_trip_metric()

    async def _maybe_transition_to_half_open(self) -> None:
        """Check whether enough time has passed to attempt recovery (called while holding _lock)."""
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            elapsed = (datetime.now(UTC) - self._opened_at).total_seconds()
            if elapsed >= self._recovery_timeout:
                self._logger.info("circuit_breaker_half_open", provider=self._name)
                self._state = CircuitState.HALF_OPEN
                self._update_gauge()

    def _update_gauge(self) -> None:
        state_value = {"CLOSED": 0, "OPEN": 1, "HALF_OPEN": 2}.get(self._state.value, 0)
        try:
            from stocktrace.infrastructure.metrics.prometheus import circuit_breaker_state  # noqa: PLC0415

            circuit_breaker_state.labels(provider=self._name).set(state_value)
        except Exception:  # noqa: BLE001
            pass

    def _emit_trip_metric(self) -> None:
        try:
            from stocktrace.infrastructure.metrics.prometheus import circuit_breaker_trips_total  # noqa: PLC0415

            circuit_breaker_trips_total.labels(provider=self._name).inc()
        except Exception:  # noqa: BLE001
            pass
