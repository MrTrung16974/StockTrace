"""Vnstock adapter for Vietnamese market indices."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from vnstock import Market

from stocktrace.application.services.market_data import MarketDataError, StockQuote


class VNStockIndexProvider:
    """Retrieve Vietnam index OHLCV data through vnstock's KBS source."""

    async def get_index_quote(self, symbol: str) -> StockQuote:
        """Return a quote based on the two latest daily OHLCV bars."""
        normalized = symbol.strip().upper()
        try:
            frame = await asyncio.to_thread(
                lambda: Market().index(symbol=normalized).ohlcv(count=2, source="kbs"),
            )
            rows = frame.to_dict(orient="records")
        except Exception as exc:
            msg = f"Could not retrieve Vietnam index {normalized}."
            raise MarketDataError(msg) from exc
        if not rows:
            msg = f"No quote found for Vietnam index {normalized}."
            raise MarketDataError(msg)

        latest = rows[-1]
        previous = rows[-2] if len(rows) > 1 else latest
        close = _decimal(latest.get("close"))
        previous_close = _decimal(previous.get("close")) or close
        if close is None or previous_close is None:
            msg = f"No close price found for Vietnam index {normalized}."
            raise MarketDataError(msg)
        change = close - previous_close
        change_percent = (
            change / previous_close * Decimal("100") if previous_close else Decimal("0")
        )
        return StockQuote(
            ticker=normalized,
            company_name=normalized,
            current_price=close,
            change=change,
            change_percent=change_percent,
            open_price=_decimal(latest.get("open")) or close,
            high_price=_decimal(latest.get("high")) or close,
            low_price=_decimal(latest.get("low")) or close,
            volume=int(latest.get("volume") or 0),
            timestamp=_timestamp(latest.get("time") or latest.get("date")),
            currency="VND",
            source="vnstock-kbs",
        )


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if hasattr(value, "to_pydatetime"):
        converted = value.to_pydatetime()
        return converted if converted.tzinfo is not None else converted.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(tz=UTC)
