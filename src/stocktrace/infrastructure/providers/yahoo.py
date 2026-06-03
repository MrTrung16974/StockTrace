"""Yahoo Finance quote provider."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast

import httpx

from stocktrace.application.services.market_data import (
    MarketDataError,
    QuoteNotFoundError,
    StockQuote,
)


class YahooFinanceQuoteProvider:
    """Retrieve latest stock quotes from Yahoo Finance chart data."""

    _base_url = "https://query1.finance.yahoo.com/v8/finance/chart"

    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds

    async def get_quote(self, symbol: str) -> StockQuote:
        """Return the latest quote for a symbol."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(
                    f"{self._base_url}/{symbol}",
                    params={"range": "1d", "interval": "1m"},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            msg = f"Could not retrieve price for {symbol}."
            raise MarketDataError(msg) from exc

        payload = response.json()
        result = _first_result(payload)
        metadata = cast(dict[str, Any], result.get("meta") or {})
        current_price = _decimal(metadata.get("regularMarketPrice"))
        if current_price is None:
            raise QuoteNotFoundError(f"No price found for {symbol}.")

        previous_close = _decimal(metadata.get("chartPreviousClose"))
        if previous_close is None:
            previous_close = current_price
        change = current_price - previous_close
        change_percent = (change / previous_close) * Decimal("100") if previous_close != Decimal("0") else Decimal("0")

        timestamp = _datetime_from_timestamp(metadata.get("regularMarketTime")) or datetime.now(tz=UTC)
        return StockQuote(
            ticker=str(metadata.get("symbol") or symbol).upper(),
            company_name=str(metadata.get("longName") or metadata.get("shortName") or symbol),
            current_price=current_price,
            change=change,
            change_percent=change_percent,
            open_price=_decimal(metadata.get("regularMarketOpen")) or current_price,
            high_price=_decimal(metadata.get("regularMarketDayHigh")) or current_price,
            low_price=_decimal(metadata.get("regularMarketDayLow")) or current_price,
            volume=int(metadata.get("regularMarketVolume") or 0),
            timestamp=timestamp,
            currency=str(metadata.get("currency") or ""),
            source="Yahoo Finance",
        )


def _first_result(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise QuoteNotFoundError("Provider returned an invalid price response.")

    chart = payload.get("chart")
    if not isinstance(chart, dict):
        raise QuoteNotFoundError("Provider returned an invalid price response.")

    result = chart.get("result")
    if not isinstance(result, list) or not result or not isinstance(result[0], dict):
        raise QuoteNotFoundError("No price found for symbol.")
    return cast(dict[str, Any], result[0])


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _datetime_from_timestamp(value: object) -> datetime | None:
    if not isinstance(value, int | float):
        return None
    return datetime.fromtimestamp(value, tz=UTC)
