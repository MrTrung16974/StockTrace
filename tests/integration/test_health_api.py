"""Health endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

HTTP_OK = 200


def test_liveness(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == HTTP_OK
    assert response.json()["status"] == "ok"


def test_readiness(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == HTTP_OK
    assert response.json()["environment"] == "test"
