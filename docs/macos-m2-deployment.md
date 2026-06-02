# macOS M2 Deployment Guide

## Goal

This guide describes how to run StockTrace on macOS Apple Silicon, especially M1/M2/M3 machines using the `arm64` architecture.

Recommended development mode:

```text
macOS M2
  |
  +--> Python app runs natively with uv
  |
  +--> PostgreSQL and Redis run in Docker Compose
```

This keeps Python fast and easy to debug while keeping infrastructure close to production.

## Architecture on macOS M2

```text
Telegram
   |
   v
StockTrace FastAPI / bot process
   |
   +--> PostgreSQL container
   |
   +--> Redis container
   |
   +--> External stock/news providers
```

Local runtime options:

```text
Option A: native Python + Docker PostgreSQL/Redis
Option B: full Docker Compose
Option C: SQLite only for quick local smoke tests
```

Recommended order:

```text
1. Native Python + SQLite for first health check
2. Native Python + Docker PostgreSQL/Redis for development
3. Full Docker Compose for production-like verification
```

## Prerequisites

Install Apple command line tools:

```bash
xcode-select --install
```

Install Homebrew if it is not installed:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Check architecture:

```bash
uname -m
```

Expected output:

```text
arm64
```

## Install Python and uv

Install Python 3.12:

```bash
brew install python@3.12
```

Install `uv`:

```bash
brew install uv
```

Check versions:

```bash
python3.12 --version
uv --version
```

Expected:

```text
Python 3.12.x
uv x.y.z
```

## Install Docker Desktop for Apple Silicon

Install Docker Desktop:

```bash
brew install --cask docker
```

Open Docker Desktop once from Applications and wait until it is running.

Check Docker:

```bash
docker version
docker compose version
```

Apple Silicon note:

- The current `postgres:16-alpine` and `redis:7-alpine` images support `arm64`.
- Do not force `linux/amd64` unless a dependency has no Apple Silicon image.
- Running `amd64` images through emulation is slower.

## Configure Environment

Create `.env`:

```bash
cp .env.example .env
```

For a quick native local run with SQLite:

```text
STOCKTRACE_ENVIRONMENT=development
STOCKTRACE_DEBUG=true
STOCKTRACE_DATABASE__URL=sqlite+aiosqlite:///./data/stocktrace.db
STOCKTRACE_REDIS__URL=redis://localhost:6379/0
```

For PostgreSQL in Docker:

```text
STOCKTRACE_DATABASE__URL=postgresql+asyncpg://stocktrace:stocktrace@localhost:5432/stocktrace
STOCKTRACE_REDIS__URL=redis://localhost:6379/0
```

For Telegram:

```text
STOCKTRACE_TELEGRAM__BOT_TOKEN=replace-with-botfather-token
STOCKTRACE_TELEGRAM__CHAT_ID=replace-with-chat-id
STOCKTRACE_TELEGRAM__ALLOWED_USER_IDS=[123456789]
```

Do not commit `.env`.

## Run Locally with SQLite

This is the fastest first check.

```bash
uv sync --extra dev
mkdir -p data
uv run uvicorn stocktrace.main:app --reload
```

Open:

```text
http://localhost:8000/health/live
http://localhost:8000/docs
```

Expected health response:

```json
{
  "status": "ok",
  "service": "StockTrace",
  "version": "0.1.0",
  "environment": "development"
}
```

## Run PostgreSQL and Redis on macOS M2

Start only infrastructure containers:

```bash
docker compose up -d postgres redis
```

Check services:

```bash
docker compose ps
```

Run migrations:

```bash
uv run alembic upgrade head
```

Start the API natively:

```bash
uv run uvicorn stocktrace.main:app --host 0.0.0.0 --port 8000 --reload
```

This development topology looks like:

```text
uvicorn on macOS arm64
      |
      +--> localhost:5432 PostgreSQL container
      |
      +--> localhost:6379 Redis container
```

## Run Full Docker Compose

Use this when you want to verify the container runtime:

```bash
docker compose up --build
```

Open:

```text
http://localhost:8000/health/live
```

Stop:

```bash
docker compose down
```

Stop and remove volumes:

```bash
docker compose down --volumes
```

Only remove volumes when you want to delete local PostgreSQL and Redis data.

## Telegram Bot on macOS M2

Local Telegram connection flow:

```text
BotFather token
      |
      v
.env
      |
      v
pydantic-settings
      |
      v
TelegramSettings
      |
      v
Telegram adapter
      |
      v
Application services
```

For local development, polling is easier than webhook:

```text
macOS StockTrace process
      |
      v
Telegram getUpdates polling
      |
      v
Command handlers
```

Why polling locally:

- No public HTTPS domain required.
- No ngrok or reverse proxy required.
- Easy to debug with breakpoints and logs.

Webhook should be used later when running behind a public HTTPS endpoint.

## Verify Telegram Token

Check bot identity:

```bash
curl "https://api.telegram.org/bot${BOT_TOKEN}/getMe"
```

If using zsh with values from `.env`, it is usually simpler to paste the token explicitly:

```bash
curl "https://api.telegram.org/bot1234567890:AA...secret.../getMe"
```

Expected:

```json
{
  "ok": true
}
```

Find chat id after sending `/start` to the bot:

```bash
curl "https://api.telegram.org/bot1234567890:AA...secret.../getUpdates"
```

## Quality Checks

After dependencies are installed:

```bash
uv run ruff check src tests
uv run black --check src tests
uv run mypy src tests
uv run pytest
```

Or:

```bash
make check
```

## Common macOS M2 Issues

### `uv` command not found

Install it:

```bash
brew install uv
```

Then restart the terminal.

### Docker is installed but `docker compose` fails

Open Docker Desktop manually and wait until the engine is running.

Check:

```bash
docker info
```

### Port already in use

Check process:

```bash
lsof -i :8000
```

Use another port:

```bash
uv run uvicorn stocktrace.main:app --port 8001 --reload
```

### PostgreSQL port conflict

If local PostgreSQL already uses `5432`, change the host port in `docker-compose.yml`:

```yaml
ports:
  - "5433:5432"
```

Then set:

```text
STOCKTRACE_DATABASE__URL=postgresql+asyncpg://stocktrace:stocktrace@localhost:5433/stocktrace
```

### Native package build problems

Prefer `uv` and Python 3.12 installed for arm64. Check:

```bash
python3.12 -c "import platform; print(platform.machine())"
```

Expected:

```text
arm64
```

If it prints `x86_64`, the terminal may be running under Rosetta.

### Telegram polling does not receive updates

Possible causes:

- You did not send `/start` to the bot.
- Another process is polling the same bot token.
- A webhook is still configured.

Reset webhook:

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/deleteWebhook"
```

## Recommended macOS M2 Daily Workflow

```bash
docker compose up -d postgres redis
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn stocktrace.main:app --reload
```

In another terminal:

```bash
uv run pytest
```

Shutdown:

```bash
docker compose down
```

## Production Notes

macOS M2 is excellent for local development, but production should usually run on:

- VPS Linux with Docker Compose.
- Managed PostgreSQL and Redis.
- Kubernetes when multi-user SaaS or high availability is needed.

Recommended production split:

```text
stocktrace-api container
stocktrace-scheduler container
postgres managed service
redis managed service
reverse proxy with TLS
secret manager
```

For a private Telegram-controlled stock monitor, a single Linux VPS with Docker Compose is enough for the first production version.
