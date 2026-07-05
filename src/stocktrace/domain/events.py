"""Domain events for the StockTrace audit system."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Base immutable domain event carrying full observability context."""

    event_id: str
    trace_id: str
    event_type: str
    aggregate_id: str       # ticker symbol, user_id, etc.
    payload: dict[str, Any]
    created_at: datetime

    @classmethod
    def create(
        cls,
        event_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        *,
        trace_id: str = "",
    ) -> "DomainEvent":
        """Convenience factory that fills bookkeeping fields automatically."""
        from stocktrace.api.middleware.correlation import get_trace_id  # noqa: PLC0415

        return cls(
            event_id=str(uuid.uuid4()),
            trace_id=trace_id or get_trace_id(),
            event_type=event_type,
            aggregate_id=aggregate_id,
            payload=payload,
            created_at=datetime.now(UTC),
        )


# ---------------------------------------------------------------------------
# Concrete events — one per meaningful state transition
# ---------------------------------------------------------------------------

def stock_requested(symbol: str, *, source: str = "api") -> DomainEvent:
    """User or scheduler requested data for a symbol."""
    return DomainEvent.create("StockRequested", symbol, {"source": source})


def quote_fetched(symbol: str, price: float, provider: str, elapsed_ms: float) -> DomainEvent:
    """A quote was successfully fetched from a provider."""
    return DomainEvent.create(
        "QuoteFetched",
        symbol,
        {"price": price, "provider": provider, "elapsed_ms": elapsed_ms},
    )


def news_fetched(symbol: str, article_count: int, provider: str) -> DomainEvent:
    """News articles were fetched for a symbol."""
    return DomainEvent.create(
        "NewsFetched",
        symbol,
        {"article_count": article_count, "provider": provider},
    )


def cache_hit(symbol: str, layer: str, data_type: str) -> DomainEvent:
    """Data was served from cache — no provider call needed."""
    return DomainEvent.create(
        "CacheHit",
        symbol,
        {"layer": layer, "data_type": data_type},
    )


def cache_miss(symbol: str, data_type: str) -> DomainEvent:
    """Cache miss — provider call required."""
    return DomainEvent.create(
        "CacheMiss",
        symbol,
        {"data_type": data_type},
    )


def alert_sent(symbol: str, chat_id: str, alert_type: str) -> DomainEvent:
    """A Telegram alert was successfully sent."""
    return DomainEvent.create(
        "AlertSent",
        symbol,
        {"chat_id": chat_id, "alert_type": alert_type},
    )


def alert_failed(symbol: str, chat_id: str, error: str) -> DomainEvent:
    """A Telegram alert failed to send."""
    return DomainEvent.create(
        "AlertFailed",
        symbol,
        {"chat_id": chat_id, "error": error},
    )


def user_command_received(user_id: int, command: str, symbol: str | None = None) -> DomainEvent:
    """A Telegram user issued a bot command."""
    return DomainEvent.create(
        "UserCommandReceived",
        str(user_id),
        {"command": command, "symbol": symbol},
    )


def scheduler_triggered(job_name: str, symbol: str) -> DomainEvent:
    """The APScheduler job fired for a symbol."""
    return DomainEvent.create(
        "SchedulerTriggered",
        symbol,
        {"job_name": job_name},
    )


def provider_circuit_opened(provider: str) -> DomainEvent:
    """A provider's circuit breaker transitioned to OPEN."""
    return DomainEvent.create(
        "ProviderCircuitOpened",
        provider,
        {"state": "OPEN"},
    )


def financial_score_improved(
    symbol: str,
    score: float,
    recommendation: str,
    reasons: list[str],
) -> DomainEvent:
    """Financial score improved for a symbol."""
    return DomainEvent.create(
        "TRACE_FINANCIAL",
        symbol,
        {
            "score": score,
            "recommendation": recommendation,
            "reasons": reasons,
            "alert_type": "score_improved",
        },
    )


def valuation_alert(symbol: str, status: str, pe: float | None) -> DomainEvent:
    """Valuation signal triggered."""
    return DomainEvent.create(
        "TRACE_VALUATION",
        symbol,
        {"status": status, "pe": pe},
    )


def cashflow_alert(symbol: str, level: str, reasons: list[str]) -> DomainEvent:
    """Cash flow signal triggered."""
    return DomainEvent.create(
        "TRACE_CASHFLOW",
        symbol,
        {"level": level, "reasons": reasons},
    )


def debt_alert(symbol: str, debt_ratio: float, level: str) -> DomainEvent:
    """Debt signal triggered."""
    return DomainEvent.create(
        "TRACE_DEBT",
        symbol,
        {"debt_ratio": debt_ratio, "level": level},
    )


def growth_alert(symbol: str, growth_pct: float, level: str) -> DomainEvent:
    """Growth signal triggered."""
    return DomainEvent.create(
        "TRACE_GROWTH",
        symbol,
        {"growth_pct": growth_pct, "level": level},
    )


def risk_alert(symbol: str, level: str, reasons: list[str]) -> DomainEvent:
    """Risk signal triggered."""
    return DomainEvent.create(
        "TRACE_RISK",
        symbol,
        {"level": level, "reasons": reasons},
    )
