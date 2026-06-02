# StockTrace

StockTrace is an enterprise-style async stock monitoring platform controlled primarily through Telegram. The platform is designed around Clean Architecture and Hexagonal Architecture so providers, persistence, notifications, scheduler execution, and future AI/event systems can evolve independently.

## Phase 0 Contents

- Architecture documentation: `architecture.md`, `data-flow.md`, `scaling-strategy.md`
- Project skeleton under `src/stocktrace`
- Production-grade typed configuration with `pydantic-settings`
- Minimal FastAPI application with health endpoints
- Structured logging and request timing middleware
- Docker, Docker Compose, Alembic, pytest, ruff, mypy, black, pre-commit setup

## Local Setup

```bash
cp .env.example .env
uv sync --extra dev
uv run uvicorn stocktrace.main:app --reload
```

Open:

- API health: `http://localhost:8000/health/live`
- Swagger: `http://localhost:8000/docs`

## Docker Setup

```bash
cp .env.example .env
docker compose up --build
```

## Coding Standard

- `ruff` enforces lint rules and import sorting.
- `black` owns formatting.
- `mypy --strict` enforces typed boundaries.
- `pytest` runs async-ready tests with an 80% coverage gate.
- `pre-commit` runs the same checks before commits.

## Configuration Strategy

Configuration is loaded by `pydantic-settings` in this order:

```text
explicit init values
environment variables
.env file
typed defaults
```

Nested environment variables use `__`:

```text
STOCKTRACE_DATABASE__URL=postgresql+asyncpg://stocktrace:stocktrace@postgres:5432/stocktrace
STOCKTRACE_TELEGRAM__BOT_TOKEN=...
```

Secrets use `SecretStr` so accidental logs do not reveal full values.

## Architecture Documents

- [architecture.md](architecture.md)
- [data-flow.md](data-flow.md)
- [scaling-strategy.md](scaling-strategy.md)
- [docs/phase-0-foundation.md](docs/phase-0-foundation.md)
- [docs/project-structure.md](docs/project-structure.md)
- [docs/deployment-guide.md](docs/deployment-guide.md)
- [docs/macos-m2-deployment.md](docs/macos-m2-deployment.md)
- [docs/telegram-bot-setup.md](docs/telegram-bot-setup.md)

## Phase Roadmap

```text
Phase 1: pure domain layer
Phase 2: async persistence and migrations
Phase 3: stock provider abstraction and failover
Phase 4: news aggregation and deduplication
Phase 5: cache abstraction
Phase 6: alert engine
Phase 7: Telegram notification and commands
Phase 8: scheduler jobs
Phase 9: business REST API, security, metrics, tracing
Phase 10: tests, Docker hardening, deployment guide, extension plugins
```
