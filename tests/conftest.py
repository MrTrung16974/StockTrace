"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from stocktrace.api.app import create_app
from stocktrace.infrastructure.config.test import load_test_settings


@pytest.fixture
def client() -> TestClient:
    """Create a test HTTP client."""
    app = create_app(settings=load_test_settings())
    return TestClient(app)
