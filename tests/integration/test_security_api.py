"""API security middleware tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import SecretStr

from stocktrace.api.app import create_app
from stocktrace.infrastructure.config.test import load_test_settings

HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_TOO_MANY_REQUESTS = 429


def test_health_is_public_when_api_key_is_configured() -> None:
    settings = load_test_settings()
    settings.security.api_key = SecretStr("test-secret")
    client = TestClient(create_app(settings=settings))

    response = client.get("/health/live")

    assert response.status_code == HTTP_OK


def test_protected_endpoint_requires_api_key() -> None:
    settings = load_test_settings()
    settings.security.api_key = SecretStr("test-secret")
    client = TestClient(create_app(settings=settings))

    response = client.get("/system/status")

    assert response.status_code == HTTP_UNAUTHORIZED


def test_protected_endpoint_accepts_valid_api_key() -> None:
    settings = load_test_settings()
    settings.security.api_key = SecretStr("test-secret")
    client = TestClient(create_app(settings=settings))

    response = client.get("/system/status", headers={"X-API-Key": "test-secret"})

    assert response.status_code == HTTP_OK
    assert response.json()["service"] == "StockTrace"


def test_rate_limit_runs_before_api_key_validation() -> None:
    settings = load_test_settings()
    settings.security.api_key = SecretStr("test-secret")
    settings.security.rate_limit_per_minute = 1
    client = TestClient(create_app(settings=settings))

    first = client.get("/system/status")
    second = client.get("/system/status")

    assert first.status_code == HTTP_UNAUTHORIZED
    assert second.status_code == HTTP_TOO_MANY_REQUESTS
