"""Trace API endpoint tests."""

from __future__ import annotations

HTTP_OK = 200


def test_trace_sources_endpoint_returns_official_catalog(client) -> None:
    response = client.get("/api/v1/trace/sources")

    assert response.status_code == HTTP_OK
    body = response.json()
    codes = {item["code"] for item in body}

    assert {"VNX", "HOSE", "HNX", "SSC", "VSDC", "SBV", "GSO", "MOF"}.issubset(codes)
    assert all(item["official"] for item in body)
