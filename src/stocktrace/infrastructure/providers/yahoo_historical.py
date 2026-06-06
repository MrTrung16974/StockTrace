"""Yahoo Finance historical price provider."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, ClassVar, cast

import httpx

from stocktrace.ai.models import HistoricalPoint
from stocktrace.infrastructure.logging.config import get_logger
from stocktrace.infrastructure.providers.yahoo import (
    MIN_VN_SYMBOL_LENGTH,
    MAX_VN_SYMBOL_LENGTH,
    _candidate_symbols,
    _decimal,
    _first_result,
)

_MAX_POINTS = 10


class YahooHistoricalProvider:
    """Fetch recent daily closes from Yahoo Finance chart API."""

    _base_url = "https://query1.finance.yahoo.com/v8/finance/chart"
    _headers: ClassVar[dict[str, str]] = {
        "Accept": "application/json",
        "User-Agent": "StockTrace/0.1",
    }

    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds
        self._logger = get_logger(__name__)

    async def get_recent(self, symbol: str, days: int = 30) -> list[HistoricalPoint]:
        """Return up to 10 most recent daily observations."""
        normalized = symbol.strip().upper()
        for candidate in _candidate_symbols(normalized):
            points = await self._fetch_history(candidate)
            if points:
                return points[-_MAX_POINTS:]

        if _looks_like_vietnam_symbol(normalized):
            points = await self._fetch_history(f"{normalized}.VN")
            if points:
                return points[-_MAX_POINTS:]

        self._logger.warning("historical_data_unavailable", symbol=normalized)
        return []

    async def _fetch_history(self, symbol: str) -> list[HistoricalPoint]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(
                    f"{self._base_url}/{symbol}",
                    params={"range": "1mo", "interval": "1d"},
                    headers=self._headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            self._logger.warning("historical_fetch_failed", symbol=symbol, error=str(exc))
            return []

        return _parse_chart_history(response.json())


def _parse_chart_history(payload: object) -> list[HistoricalPoint]:
    try:
        result = _first_result(payload)
    except Exception:
        return []

    timestamps = cast(list[Any], result.get("timestamp") or [])
    indicators = cast(dict[str, Any], result.get("indicators") or {})
    quote_rows = cast(list[dict[str, Any]], indicators.get("quote") or [])
    if not quote_rows:
        return []

    closes = cast(list[Any], quote_rows[0].get("close") or [])
    points: list[HistoricalPoint] = []
    previous_close: Decimal | None = None

    for index, timestamp in enumerate(timestamps):
        if index >= len(closes):
            break
        close = _decimal(closes[index])
        if close is None or not isinstance(timestamp, int | float):
            continue

        change_percent = Decimal("0")
        if previous_close is not None and previous_close != Decimal("0"):
            change_percent = ((close - previous_close) / previous_close) * Decimal("100")

        points.append(
            HistoricalPoint(
                day=datetime.fromtimestamp(timestamp, tz=UTC).date(),
                close=close,
                change_percent=change_percent,
            ),
        )
        previous_close = close

    return points


def _looks_like_vietnam_symbol(symbol: str) -> bool:
    normalized = symbol.strip().upper()
    return (
        "." not in normalized
        and normalized.isalpha()
        and MIN_VN_SYMBOL_LENGTH <= len(normalized) <= MAX_VN_SYMBOL_LENGTH
    )
