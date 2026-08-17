"""Tests for the presentation-only suggestion explanation REST endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

_HTTP_OK = 200


def test_explain_suggestion_endpoint_returns_data_only_when_ai_is_disabled(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/suggestions/explain",
        json={
            "symbol": "HPG",
            "action": "ACCUMULATE_CONDITIONALLY",
            "horizon": "MEDIUM",
            "risk_level": "MEDIUM",
            "confidence": "0.75",
            "evidence": [
                {
                    "factor_code": "FINANCIAL_SCORE",
                    "label": "Điểm tài chính",
                    "value": "0.75",
                    "direction": "SUPPORTS",
                    "source": "vnstock",
                    "observed_at": "2026-08-12T09:00:00+00:00",
                }
            ],
            "freshness": [
                {
                    "data_type": "quote",
                    "source": "exchange-feed",
                    "observed_at": "2026-08-12T09:00:00+00:00",
                    "ttl_seconds": 300,
                }
            ],
            "invalidation_conditions": [
                {"code": "STALE", "description": "Dữ liệu đã cũ."}
            ],
            "rule_version": "suggestion-rules-v1",
            "generated_at": "2026-08-12T09:00:00+00:00",
            "suggestion_id": "suggestion-api-1",
        },
    )

    assert response.status_code == _HTTP_OK
    body = response.json()
    assert body["suggestion"]["action"] == "ACCUMULATE_CONDITIONALLY"
    assert body["ai_status"] == "AI_UNAVAILABLE"
    assert "FINANCIAL_SCORE" in body["explanation"]
    assert "quantity" not in body
    assert "price" not in body
