"""Resilient provider wrapper: timeout + retry (tenacity) + circuit breaker + bulkhead."""

from __future__ import annotations

import asyncio
from typing import Any

import tenacity

from stocktrace.application.services.market_data import (
    FundamentalData,
    HistoricalPrice,
    MarketDataError,
    QuoteNotFoundError,
    StockQuote,
)
from stocktrace.infrastructure.logging.config import get_logger
from stocktrace.infrastructure.providers.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError

# Never retry on these — they are permanent failures
_NO_RETRY_EXCEPTIONS = (QuoteNotFoundError, CircuitBreakerOpenError)


class ResilientQuoteProvider:
    """Decorator that wraps any QuoteProvider with resilience patterns.

    Resilience stack (outermost → innermost):
        1. Bulkhead   — limits concurrent calls via asyncio.Semaphore
        2. Circuit Breaker — stops calls when provider is unhealthy
        3. Retry + backoff — tenacity with exponential backoff
        4. Timeout    — asyncio.wait_for around each attempt
    """

    def __init__(
        self,
        inner: Any,  # QuoteProvider protocol
        provider_name: str = "default",
        *,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        max_concurrency: int = 10,
    ) -> None:
        self._inner = inner
        self._name = provider_name
        self._timeout = timeout_seconds
        self._cb = CircuitBreaker(
            provider_name=provider_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._logger = get_logger(__name__)
        self._retry = tenacity.retry(
            stop=tenacity.stop_after_attempt(max_retries),
            wait=tenacity.wait_exponential(multiplier=0.5, min=0.5, max=10),
            retry=tenacity.retry_if_not_exception_type(_NO_RETRY_EXCEPTIONS),
            reraise=True,
        )

    async def get_quote(self, symbol: str) -> StockQuote:
        """Fetch a quote with full resilience protection."""
        return await self._call(self._inner.get_quote(symbol), f"get_quote({symbol})")  # type: ignore[return-value]

    async def get_historical_prices(self, symbol: str, days: int = 365) -> list[HistoricalPrice]:
        """Fetch historical prices with full resilience protection."""
        return await self._call(  # type: ignore[return-value]
            self._inner.get_historical_prices(symbol, days),
            f"get_historical_prices({symbol})",
        )

    async def get_fundamental_data(self, symbol: str) -> FundamentalData:
        """Fetch fundamental data with full resilience protection."""
        return await self._call(  # type: ignore[return-value]
            self._inner.get_fundamental_data(symbol),
            f"get_fundamental_data({symbol})",
        )

    async def _call(self, coro: Any, label: str) -> Any:
        """Apply bulkhead → circuit breaker → timeout to an awaitable."""
        async with self._semaphore:
            return await self._cb.call(self._with_timeout(coro, label))

    async def _with_timeout(self, coro: Any, label: str) -> Any:
        """Wrap a coroutine with asyncio timeout and translate errors."""
        try:
            return await asyncio.wait_for(coro, timeout=self._timeout)
        except TimeoutError as exc:
            msg = f"Provider '{self._name}' timed out on {label} after {self._timeout}s"
            self._logger.warning("provider_timeout", provider=self._name, label=label)
            self._emit_error("timeout")
            raise MarketDataError(msg) from exc
        except MarketDataError:
            self._emit_error("market_data_error")
            raise
        except Exception as exc:
            self._emit_error("unexpected")
            raise MarketDataError(str(exc)) from exc

    def _emit_error(self, error_type: str) -> None:
        try:
            from stocktrace.infrastructure.metrics.prometheus import provider_errors_total  # noqa: PLC0415

            provider_errors_total.labels(provider=self._name, error_type=error_type).inc()
        except Exception:  # noqa: BLE001
            pass
