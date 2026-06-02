# Deployment Guide

## Local

```bash
cp .env.example .env
uv sync --extra dev
uv run uvicorn stocktrace.main:app --reload
```

For Apple Silicon machines, see `docs/macos-m2-deployment.md`.

Health endpoints:

```text
GET http://localhost:8000/health/live
GET http://localhost:8000/health/ready
```

## Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

Services:

- `api`: FastAPI application.
- `postgres`: durable production-style database.
- `redis`: cache and future distributed coordination.

Volumes:

- `postgres_data`: PostgreSQL data.
- `redis_data`: Redis append-only data.

Restart policy:

- `unless-stopped` for all runtime services.

## VPS

Recommended baseline:

```text
2 CPU
2-4 GB RAM
Docker Engine
Docker Compose plugin
Firewall allowing 22 and 8000 or reverse proxy ports
```

Deployment flow:

```text
git pull
copy production .env
docker compose pull
docker compose up -d --build
docker compose logs -f api
```

For public access, place Nginx or Caddy in front of the API and terminate TLS there.

## Docker Swarm Future

```text
manager node
    |
    +--> replicated API service
    +--> singleton scheduler service
    +--> PostgreSQL external managed service
    +--> Redis external managed service
```

Use Docker secrets for Telegram tokens and API keys.

## Kubernetes Future

```text
Ingress
  |
  v
Deployment: stocktrace-api
  |
  +--> Secret: stocktrace-secrets
  +--> ConfigMap: stocktrace-config
  +--> Service: stocktrace-api
  +--> CronJob or Deployment: stocktrace-scheduler
  +--> External PostgreSQL
  +--> External Redis
```

Recommended later additions:

- HorizontalPodAutoscaler for API.
- PodDisruptionBudget.
- NetworkPolicy.
- ExternalSecrets integration.
- OpenTelemetry collector.
