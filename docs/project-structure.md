# Project Structure

```text
.
├── .editorconfig
├── .env.example
├── .github/
│   └── workflows/
│       └── ci.yml
├── .gitignore
├── .pre-commit-config.yaml
├── Dockerfile
├── Makefile
├── README.md
├── alembic.ini
├── architecture.md
├── data-flow.md
├── docker-compose.yml
├── docs/
│   ├── phase-0-foundation.md
│   └── project-structure.md
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py
├── pyproject.toml
├── requirements.txt
├── scaling-strategy.md
├── scripts/
│   └── init_db.py
├── src/
│   └── stocktrace/
│       ├── api/
│       │   ├── app.py
│       │   ├── dependencies.py
│       │   ├── middleware/
│       │   │   └── request_timing.py
│       │   ├── routers/
│       │   │   └── health.py
│       │   └── schemas/
│       │       └── health.py
│       ├── application/
│       │   ├── commands/
│       │   ├── queries/
│       │   └── services/
│       │       └── health.py
│       ├── bootstrap/
│       │   └── container.py
│       ├── domain/
│       │   ├── entities/
│       │   ├── repositories/
│       │   ├── services/
│       │   └── value_objects/
│       ├── infrastructure/
│       │   ├── cache/
│       │   ├── config/
│       │   │   ├── dev.py
│       │   │   ├── prod.py
│       │   │   ├── settings.py
│       │   │   └── test.py
│       │   ├── db/
│       │   │   ├── base.py
│       │   │   └── session.py
│       │   ├── logging/
│       │   │   └── config.py
│       │   ├── metrics/
│       │   │   └── timing.py
│       │   ├── news/
│       │   ├── notifications/
│       │   ├── providers/
│       │   ├── scheduler/
│       │   ├── security/
│       │   └── tracing/
│       │       └── hooks.py
│       └── main.py
└── tests/
    ├── conftest.py
    ├── integration/
    │   └── test_health_api.py
    └── unit/
        └── test_config.py
```
