# Phase 0: Architecture and Project Foundation

## Goal

Create the enterprise foundation for StockTrace before implementing business modules. This phase delivers:

- Architecture documentation.
- Standard Python project structure.
- Typed production-grade configuration.
- Minimal FastAPI health API.
- Dependency injection composition root.
- Structured logging and timing middleware.
- Docker, Alembic, pytest, ruff, mypy, black, pre-commit, and CI skeleton.

## Architecture Decision

StockTrace uses Clean Architecture with Hexagonal Architecture:

```text
API / Telegram / Scheduler
        |
        v
Application Services
        |
        v
Domain Layer
        |
        v
Ports: repositories, providers, cache, notifier
        |
        v
Infrastructure Adapters
```

The application is prepared for CQRS by separating `application/commands` and `application/queries`. Event-driven migration is prepared by keeping scheduler/provider/news/notification boundaries explicit.

## Source Code Delivered

Key files:

- `pyproject.toml`: project metadata, dependencies, ruff, black, mypy, pytest config.
- `requirements.txt`: runtime dependencies for Docker.
- `Makefile`: local development commands.
- `.pre-commit-config.yaml`: local quality gate.
- `Dockerfile` and `docker-compose.yml`: production-like local runtime.
- `alembic.ini`, `migrations/env.py`: async migration foundation.
- `src/stocktrace/main.py`: ASGI entrypoint.
- `src/stocktrace/api/app.py`: FastAPI app factory.
- `src/stocktrace/infrastructure/config/settings.py`: typed settings.
- `src/stocktrace/bootstrap/container.py`: dependency composition root.
- `tests/`: initial config and health API tests.

## Request Flow

```text
HTTP request
    |
    v
RequestTimingMiddleware
    |
    v
FastAPI router
    |
    v
Dependency resolver
    |
    v
Container
    |
    v
HealthCheckService
    |
    v
Pydantic response schema
```

## Dependency Injection

The `Container` is created from a `Settings` instance and attached to `app.state`.

```text
Settings
   |
   v
Container
   |
   +--> HealthCheckService
   +--> future repositories
   +--> future providers
   +--> future cache
   +--> future notifier
   +--> future scheduler
```

Tests can create a FastAPI app with test settings, which prevents global configuration leakage.

## Configuration Loading

Configuration is loaded by `pydantic-settings`.

```text
explicit Settings(...) values
        |
        v
environment variables
        |
        v
.env
        |
        v
typed defaults
```

Nested env variables use `__`, for example:

```text
STOCKTRACE_DATABASE__URL=postgresql+asyncpg://stocktrace:stocktrace@postgres:5432/stocktrace
STOCKTRACE_TELEGRAM__BOT_TOKEN=...
```

Production mode validates required secrets:

- Telegram bot token.
- Telegram chat id.
- API key placeholder.

## Scalability Strategy

Phase 0 keeps the API stateless and async. Later phases can scale independently:

- API instances scale horizontally behind a load balancer.
- Scheduler can move to a dedicated singleton container.
- Provider fetching can use bounded async concurrency.
- Redis can absorb repeated quote/news reads.
- PostgreSQL remains the durable source of truth.

## Future Extension Strategy

Prepared extension points:

- `domain`: entities, value objects, invariants.
- `application/commands`: write use cases.
- `application/queries`: read use cases.
- `infrastructure/providers`: stock provider adapters.
- `infrastructure/news`: news feed adapters.
- `infrastructure/cache`: Redis and memory cache.
- `infrastructure/notifications`: Telegram notifier.
- `infrastructure/scheduler`: APScheduler jobs.
- `infrastructure/security`: authorization and rate limit policies.

## Best Practices

- Domain stays pure.
- Settings are typed and validated.
- Secrets use `SecretStr`.
- App construction is factory-based for testing.
- Tooling is declared in `pyproject.toml`.
- CI runs lint, format check, type check, and tests.
- Docker health checks target `/health/live`.

## Verification

Completed:

- `python3 -m compileall src scripts tests`

Blocked by missing local tools/dependencies:

- `uv` is not installed.
- `ruff` is not installed.
- `mypy` is not installed.
- `pytest` cannot run because runtime dependency `structlog` is not installed.
