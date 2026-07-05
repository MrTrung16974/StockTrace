"""Integration tests for financial API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from stocktrace.api.app import create_app
from stocktrace.infrastructure.config.test import load_test_settings


@pytest.fixture
def client() -> TestClient:
    app = create_app(settings=load_test_settings())
    return TestClient(app)


def test_financial_analysis_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/financial/FPT/analysis?period=1Y")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "FPT"
    assert data["company_name"] == "FPT CORPORATION"
    assert "financial_score" in data
    assert "recommendation" in data
    assert len(data["charts"]) == 5


def test_financial_report_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/financial/FPT/report")
    assert response.status_code == 200
    assert response.json()["symbol"] == "FPT"


def test_financial_compare_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/financial/compare/FPT/CMG")
    assert response.status_code == 200
    data = response.json()
    assert data["winner"] in ("FPT", "CMG")
    assert data["symbol_a"]["symbol"] == "FPT"
    assert data["symbol_b"]["symbol"] == "CMG"


def test_financial_unknown_symbol(client: TestClient) -> None:
    response = client.get("/api/v1/financial/UNKNOWN/analysis")
    assert response.status_code == 404
