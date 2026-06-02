# StockTrace Architecture

## Phase 0 Scope

Phase 0 defines the enterprise architecture, project skeleton, production-grade configuration system, observability hooks, and a minimal runnable FastAPI health surface. Business modules are intentionally introduced in later phases so each boundary can be implemented and tested cleanly.

## Architecture Goals

- Monitor stock prices, news, watchlists, alert rules, and provider health.
- Control the platform primarily through a Telegram bot.
- Expose a FastAPI backend for operations, integrations, dashboards, and future SaaS use.
- Keep the domain model pure and independent from databases, HTTP clients, Telegram SDKs, schedulers, or cloud infrastructure.
- Support future migration to CQRS, Kafka, Celery workers, vector search, AI summarization, portfolio management, and trading automation.

## High-Level Component Diagram

```text
                         +----------------------+
                         |      Telegram UI     |
                         | /add /remove /price  |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         | Telegram Bot Adapter |
                         | handlers/middleware  |
                         +----------+-----------+
                                    |
                                    v
+----------------+       +----------------------+       +----------------------+
| REST Clients   +------>|      FastAPI API     |------>| Application Services |
| Dashboard/CLI  |       | routers/dependencies |       | commands/queries     |
+----------------+       +----------+-----------+       +----------+-----------+
                                    |                              |
                                    |                              v
                                    |                   +----------------------+
                                    |                   |     Domain Layer     |
                                    |                   | entities/services    |
                                    |                   +----------+-----------+
                                    |                              |
                                    v                              v
                         +----------------------+       +----------------------+
                         | Scheduler Adapter    |------>| Ports / Interfaces   |
                         | APScheduler jobs     |       | repositories/providers|
                         +----------+-----------+       +----------+-----------+
                                    |                              |
                                    v                              v
                         +-----------------------------------------------+
                         |              Infrastructure Adapters           |
                         | SQLAlchemy | Redis | Yahoo | RSS | Telegram   |
                         +----------------------+------------------------+
                                                |
                                                v
                         +----------------------+------------------------+
                         | PostgreSQL | SQLite | Redis | External APIs   |
                         +-----------------------------------------------+
```

## Clean Architecture

Clean Architecture keeps business rules at the center and dependencies pointing inward.

```text
Outer detail                                             Inner policy

+--------------------------------------------------------------------+
| API, Telegram, Scheduler, SQLAlchemy, Redis, HTTP providers         |
|  depend on                                                        |
| +----------------------------------------------------------------+ |
| | Application use cases: commands, queries, orchestration          | |
| |  depend on                                                      | |
| | +------------------------------------------------------------+ | |
| | | Domain: entities, value objects, domain services, contracts | | |
| | +------------------------------------------------------------+ | |
| +----------------------------------------------------------------+ |
+--------------------------------------------------------------------+
```

The domain does not import FastAPI, SQLAlchemy, Redis, APScheduler, Telegram SDKs, or provider SDKs. Infrastructure implements contracts defined by the domain/application layers.

## Hexagonal Architecture

StockTrace uses ports and adapters:

- Inbound adapters: Telegram handlers, FastAPI routers, scheduler jobs.
- Application ports: use-case services that coordinate domain behavior.
- Outbound ports: repository contracts, stock provider contracts, news provider contracts, cache contracts, notifier contracts.
- Outbound adapters: SQLAlchemy repositories, Redis cache, memory cache, Yahoo/Finnhub/AlphaVantage/VNStock providers, RSS fetchers, Telegram sender.

```text
Inbound Adapter         Application Port          Domain              Outbound Port          Adapter

Telegram Command
      |
      v
Telegram Handler
      |
      v
Application Service
      |
      v
Domain Entity / Service
      |
      v
Repository / Provider Protocol
      |
      v
SQLAlchemy / HTTP / Redis / Telegram implementation
```

## Why Split Domain, Application, Infrastructure

- `domain`: pure business model. It is stable, easy to test, and reusable across API, bot, scheduler, and workers.
- `application`: use-case orchestration. It coordinates repositories, providers, transactions, notifications, and policies without owning external implementation details.
- `infrastructure`: replaceable technical adapters. Databases, caches, provider APIs, HTTP clients, Telegram SDKs, logging, metrics, and schedulers live here.

This separation lets the platform change PostgreSQL to another database, add Kafka, replace a stock provider, or move jobs to Celery without rewriting business rules.

## Repository Pattern

Repository contracts hide persistence details behind domain-friendly methods.

```text
Application Service
      |
      v
WatchlistRepository Protocol
      |
      +--> SQLAlchemyWatchlistRepository
      +--> InMemoryWatchlistRepository for tests
      +--> Future EventSourcedWatchlistRepository
```

Benefits:

- Domain entities are not SQLAlchemy rows.
- Tests can use in-memory repositories.
- Transaction boundaries can later move into a Unit of Work.
- Multi-tenant SaaS partitioning can be added at repository level.

## Provider Abstraction

Stock market data providers differ in API shape, rate limits, coverage, reliability, and pricing. StockTrace uses provider protocols and a provider manager.

```text
Application Service
      |
      v
StockProvider Protocol
      |
      +--> YahooFinanceProvider
      +--> FinnhubProvider
      +--> AlphaVantageProvider
      +--> VNStockProvider
      |
      v
ProviderManager: retry, timeout, rate limit, circuit breaker, health score
```

The application asks for a quote; it does not care which external vendor answered.

## Async Architecture

StockTrace is I/O heavy:

- HTTP calls to stock providers.
- RSS/news crawling.
- Telegram send operations.
- PostgreSQL queries.
- Redis cache operations.
- Scheduler jobs.

Async I/O lets one process keep many requests and jobs in flight without blocking threads. This is important for concurrent fetching, failover chains, bot responsiveness, and API latency.

## CQRS Future Support

Phase 0 keeps application folders split into `commands` and `queries`.

```text
Command side                         Query side

AddWatchlistItemCommand              GetWatchlistQuery
EvaluateAlertRulesCommand            GetLatestNewsQuery
CreateAlertRuleCommand               GetProviderHealthQuery
        |                                      |
        v                                      v
Write repositories                    Read models / projections
        |                                      |
        +----------------+---------------------+
                         |
                         v
                  Domain events
```

Future CQRS migration path:

- Keep commands transactional and domain-focused.
- Add read-optimized projections for dashboards.
- Publish domain events after command success.
- Move expensive read aggregation to workers.

## Event-Driven Future Support

The initial platform can run synchronously in one service. Event boundaries are still explicit so Kafka or another event bus can be added later.

```text
QuoteFetched
      |
      +--> AlertEvaluationRequested
      +--> WatchlistSnapshotUpdated
      +--> ProviderHealthUpdated

NewsArticleFetched
      |
      +--> NewsDeduplicated
      +--> BreakingNewsAlertRequested
      +--> FutureSummarizationRequested
```

Migration path:

1. Start with in-process application events.
2. Add an event bus port.
3. Implement KafkaEventBus in infrastructure.
4. Move scheduler jobs to Celery or distributed workers.
5. Build read projections and AI pipelines from event streams.

## Dependency Graph

```text
stocktrace.main
  -> stocktrace.api.app
      -> stocktrace.api.routers
      -> stocktrace.bootstrap.container
          -> stocktrace.infrastructure.config
          -> stocktrace.application.services
              -> stocktrace.domain

Allowed dependencies:

api              -> application, infrastructure.config, bootstrap
bootstrap        -> application, infrastructure
application      -> domain
infrastructure   -> domain, application contracts
domain           -> Python standard library only
```

## Trust Zones

```text
Untrusted Internet
  |
  v
FastAPI boundary: validation, auth placeholder, rate limit middleware
  |
  v
Application boundary: authorization decisions, use-case validation
  |
  v
Domain boundary: invariants
  |
  v
Infrastructure boundary: sanitized SQL parameters, secret-aware clients
```

Telegram is semi-trusted only after whitelist verification. Provider responses are untrusted input and must be validated before entering domain entities.

## Phase Roadmap

```text
Phase 0: Architecture, project foundation, config, health API
Phase 1: Pure domain layer: entities, value objects, repository contracts, domain services
Phase 2: Persistence: SQLAlchemy async, migrations, repositories, unit-of-work foundation
Phase 3: Provider system: providers, retry, timeout, rate limits, failover, health scoring
Phase 4: News aggregation: feeds, parsing, dedupe, sentiment placeholder, cache integration
Phase 5: Cache: Redis and memory adapters with TTL and invalidation strategy
Phase 6: Alert engine: rules, cooldown, debounce, priority, suppression
Phase 7: Notification and Telegram command control plane
Phase 8: Scheduler jobs and operational lifecycle
Phase 9: FastAPI business endpoints, security, metrics, tracing
Phase 10: Tests, Docker hardening, deployment guide, extension plugins
```
