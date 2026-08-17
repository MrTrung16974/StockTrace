"""Prometheus metrics registry for StockTrace."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------

requests_total = Counter(
    "stocktrace_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

provider_errors_total = Counter(
    "stocktrace_provider_errors_total",
    "Total provider errors",
    ["provider", "error_type"],
)

cache_hits_total = Counter(
    "stocktrace_cache_hits_total",
    "Total cache hits",
    ["layer"],  # L1, L2
)

cache_misses_total = Counter(
    "stocktrace_cache_misses_total",
    "Total cache misses",
    [],
)

alerts_sent_total = Counter(
    "stocktrace_alerts_sent_total",
    "Total Telegram alerts sent",
    ["symbol"],
)

alerts_failed_total = Counter(
    "stocktrace_alerts_failed_total",
    "Total Telegram alerts that failed",
    ["symbol"],
)

circuit_breaker_trips_total = Counter(
    "stocktrace_circuit_breaker_trips_total",
    "Total circuit breaker open transitions",
    ["provider"],
)

audit_events_total = Counter(
    "stocktrace_audit_events_total",
    "Total domain events emitted",
    ["event_type"],
)

# ---------------------------------------------------------------------------
# Histograms
# ---------------------------------------------------------------------------

request_duration_seconds = Histogram(
    "stocktrace_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

provider_latency_seconds = Histogram(
    "stocktrace_provider_latency_seconds",
    "External market data provider latency",
    ["provider"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

telegram_latency_seconds = Histogram(
    "stocktrace_telegram_latency_seconds",
    "Telegram API call latency",
    [],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

cache_operation_seconds = Histogram(
    "stocktrace_cache_operation_seconds",
    "Cache get/set operation latency",
    ["operation", "layer"],
    buckets=(0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1),
)

# ---------------------------------------------------------------------------
# Gauges
# ---------------------------------------------------------------------------

scheduler_jobs_active = Gauge(
    "stocktrace_scheduler_jobs_active",
    "Number of currently active scheduler jobs",
)

watchlist_symbols_total = Gauge(
    "stocktrace_watchlist_symbols_total",
    "Total symbols across all watchlists",
)

circuit_breaker_state = Gauge(
    "stocktrace_circuit_breaker_state",
    "Circuit breaker state (0=CLOSED, 1=OPEN, 2=HALF_OPEN)",
    ["provider"],
)

auto_trade_gate_decisions_total = Counter(
    "stocktrace_auto_trade_gate_decisions_total",
    "Auto-trade gate decisions by outcome and first block reason",
    ["outcome", "block_code"],
)

auto_trade_kill_switch_active = Gauge(
    "stocktrace_auto_trade_kill_switch_active",
    "Global auto-trade kill switch state (1=active, 0=inactive)",
)

auto_trade_rollout_percentage = Gauge(
    "stocktrace_auto_trade_rollout_percentage",
    "Percentage of deterministically enrolled auto-trade pilot owners",
)
