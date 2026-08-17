"""Security regression tests for the emergency auto-trade control surface."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import SecretStr

from stocktrace.api.app import create_app
from stocktrace.infrastructure.config.test import load_test_settings

HTTP_NOT_FOUND = 404


def test_auto_trade_control_has_stop_only_surface_without_a_release_endpoint() -> None:
    settings = load_test_settings()
    settings.security.api_key = SecretStr("api-key")
    settings.auto_trade.control_key = SecretStr("control-key")
    settings.auto_trade.control_operator_id = "risk-operator-1"
    client = TestClient(create_app(settings=settings))
    headers = {"X-API-Key": "api-key", "X-Auto-Trade-Control-Key": "control-key"}

    response = client.post("/api/v1/system/auto-trade/kill-switch/deactivate", headers=headers)

    assert response.status_code == HTTP_NOT_FOUND
