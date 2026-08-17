"""Integration tests for the double-authenticated emergency kill-switch endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import SecretStr

from stocktrace.api.app import create_app
from stocktrace.infrastructure.config.test import load_test_settings

HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403


def _client() -> TestClient:
    settings = load_test_settings()
    settings.security.api_key = SecretStr("api-key")
    settings.auto_trade.control_key = SecretStr("control-key")
    settings.auto_trade.control_operator_id = "risk-operator-1"
    return TestClient(create_app(settings=settings))


def test_kill_switch_requires_global_and_dedicated_control_keys() -> None:
    client = _client()
    path = "/api/v1/system/auto-trade/kill-switch/activate"

    missing_api_key = client.post(path, json={"reason": "stop"})
    missing_control_key = client.post(
        path,
        headers={"X-API-Key": "api-key"},
        json={"reason": "stop"},
    )

    assert missing_api_key.status_code == HTTP_UNAUTHORIZED
    assert missing_control_key.status_code == HTTP_FORBIDDEN


def test_kill_switch_activation_is_immediately_visible_to_authenticated_operator() -> None:
    client = _client()
    headers = {"X-API-Key": "api-key", "X-Auto-Trade-Control-Key": "control-key"}

    activated = client.post(
        "/api/v1/system/auto-trade/kill-switch/activate",
        headers=headers,
        json={"reason": "broker reconciliation mismatch"},
    )
    observed = client.get("/api/v1/system/auto-trade/control", headers=headers)

    assert activated.status_code == HTTP_OK
    assert activated.json()["kill_switch_active"] is True
    assert observed.status_code == HTTP_OK
    assert observed.json()["kill_switch_reason"] == "broker reconciliation mismatch"
