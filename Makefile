.PHONY: install install-dev run test lint format typecheck check pre-commit migrate db-up db-down docker-build docker-up docker-down

PYTHON ?= python
UV ?= uv

install:
	$(UV) sync

install-dev:
	$(UV) sync --extra dev
	$(UV) run pre-commit install

run:
	$(UV) run uvicorn stocktrace.main:app --host 0.0.0.0 --port 8000 --reload

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check src tests

format:
	$(UV) run ruff check src tests --fix
	$(UV) run black src tests

typecheck:
	$(UV) run mypy src tests

check: lint typecheck test

pre-commit:
	$(UV) run pre-commit run --all-files

migrate:
	$(UV) run alembic upgrade head

db-up:
	docker compose up -d postgres redis

db-down:
	docker compose down

docker-build:
	docker build -t stocktrace:local .

docker-up:
	docker compose up --build

docker-down:
	docker compose down --remove-orphans
