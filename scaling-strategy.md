# StockTrace Scaling Strategy

## Scaling Principles

- Keep business logic stateless wherever possible.
- Store durable state in PostgreSQL.
- Store short-lived derived state in Redis.
- Use async I/O for high concurrency.
- Isolate scheduler jobs so slow providers do not block API or Telegram command handling.
- Keep domain contracts stable while infrastructure scales out.

## Initial Deployment

```text
Single VPS / Docker Compose

+---------------------+
| stocktrace-api      |
| FastAPI + scheduler |
| Telegram bot        |
+----------+----------+
           |
           +------------------+
           |                  |
           v                  v
    +-------------+    +-------------+
    | PostgreSQL  |    | Redis       |
    +-------------+    +-------------+
```

This is enough for a private stock monitor controlled by Telegram.

## Vertical Scaling

- Increase CPU and memory for API container.
- Increase PostgreSQL memory and connection limits.
- Tune async database pool size.
- Tune provider concurrency per provider rate limit.
- Use Redis cache to reduce external API calls.

## Horizontal Scaling

```text
Load Balancer
      |
      +----------------+----------------+
      |                |                |
      v                v                v
  API Pod 1        API Pod 2        API Pod 3
      |                |                |
      +----------------+----------------+
                       |
                       v
               PostgreSQL / Redis
```

API instances can scale horizontally because request handlers are stateless. Scheduler and Telegram polling need leader election or separate worker deployment before running multiple replicas.

## Scheduler Scaling

Phase 0 starts with APScheduler in-process. Future distributed options:

```text
Option A: one scheduler replica
Option B: scheduler with distributed lock in Redis/PostgreSQL
Option C: replace scheduled execution with Celery beat + workers
Option D: event-driven jobs with Kafka consumers
```

Recommended migration:

1. In-process APScheduler for simplicity.
2. Dedicated scheduler container.
3. Redis or PostgreSQL advisory lock for singleton jobs.
4. Celery workers for heavy crawling and alert evaluation.
5. Kafka for event-stream fanout.

## Provider Scaling

```text
ProviderManager
      |
      +--> rate limit bucket per provider
      +--> timeout policy per provider
      +--> circuit breaker per provider
      +--> health score per provider
      +--> fallback chain by symbol market
```

For Vietnamese stocks, `VNStockProvider` can be preferred. For US/global stocks, Yahoo/Finnhub/AlphaVantage can be selected by availability, cost, and health score.

## Cache Strategy

```text
Read request
    |
    v
Cache lookup
    |
    +--> hit  -> return cached quote/news
    |
    +--> miss -> provider/repository fetch
                  |
                  v
               store with TTL
```

Cache layers:

- Memory cache: local development and tests.
- Redis cache: production shared cache.
- Future distributed cache warming for watchlist symbols.

Invalidation:

- Quote TTL by market volatility and provider limit.
- News TTL by feed update frequency.
- Watchlist and alert rule cache invalidated on command writes.

## Database Strategy

- PostgreSQL is the production database.
- SQLite is supported as a fallback for local development and tests.
- SQLAlchemy async keeps request and job execution non-blocking.
- Alembic owns schema migrations.
- Domain entities stay separate from ORM models to avoid persistence leakage.

Future database options:

- Read replicas for dashboards.
- TimescaleDB for quote time series.
- Partitioning by tenant or market.
- Event store for audit-heavy workflows.

## Observability Scaling

Phase 0 includes structured logging and timing middleware. Future hooks:

- Prometheus metrics endpoint.
- OpenTelemetry traces.
- Provider health dashboards.
- Alert delivery success/failure metrics.
- Scheduler job duration histograms.

## Security Scaling

Security boundaries:

```text
Internet -> API validation -> auth/rate limit -> application authorization -> domain invariants
Telegram -> whitelist -> command validation -> application authorization -> domain invariants
Providers -> response validation -> normalized domain objects
```

Future hardening:

- API keys or OAuth2 for REST clients.
- Per-user Telegram authorization.
- Tenant-aware repositories.
- Secret manager integration.
- Signed webhook verification.

## Extension Points

```text
Kafka Event Bus
  implement EventBus port and publish domain events

Celery Workers
  move scheduler job bodies into task handlers

AI Agent / LLM Summarizer
  consume NewsArticleCreated events and write summaries

Vector Database / RAG
  embed news articles and provider reports

Multi-user SaaS
  add User, Tenant, Membership, and tenant-scoped repositories

Portfolio Management
  add Portfolio, Position, Transaction, PnL services

Trading Automation
  add BrokerProvider port, risk engine, approval workflow
```

## CI/CD Future Strategy

```text
Pull request
    |
    +--> ruff
    +--> black check
    +--> mypy
    +--> pytest with coverage
    +--> build Docker image
    +--> vulnerability scan
    +--> deploy to staging
    +--> smoke tests
    +--> production deploy with rollback
```

Coverage target starts at 80%. Critical modules such as alert evaluation, provider failover, deduplication, and repositories should trend higher than the global minimum.
