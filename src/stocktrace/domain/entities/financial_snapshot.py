"""Persisted fallback representation of a financial dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class FinancialDashboardSnapshot:
    """A rendered dashboard retained after a successful financial analysis."""

    symbol: str
    period: str
    telegram_html: str
    json_payload: dict[str, Any]
    created_at: datetime
