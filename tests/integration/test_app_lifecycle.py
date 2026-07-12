"""Application lifecycle tests."""

from __future__ import annotations

import builtins

import pytest

from stocktrace.api.app import create_app, lifespan
from stocktrace.infrastructure.config.test import load_test_settings


@pytest.mark.asyncio
async def test_lifespan_initializes_and_disposes_runtime_state() -> None:
    app = create_app(settings=load_test_settings())

    async with lifespan(app):
        assert app.state.settings.environment.value == "test"
        assert app.state.container is not None
        assert app.state.telegram_runner.is_configured is False


def test_create_app_tolerates_missing_prometheus_client(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load_test_settings()
    settings.observability.prometheus_enabled = True
    real_import = builtins.__import__

    def guarded_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "prometheus_client":
            raise ModuleNotFoundError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    app = create_app(settings=settings)

    assert app.title == settings.app.name
