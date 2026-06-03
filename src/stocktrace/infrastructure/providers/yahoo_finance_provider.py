from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

import httpx

from stocktrace.domain.entities.stock_quote import StockQuote
from stocktrace.domain.ports.providers import StockProvider

logger = logging.getLogger(__name__)

_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_SUMMARY_URL = (
    "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
    "?modules=price,summaryDetail,defaultKeyStatistics"
)
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; StockTrace/0.1)",
    "Accept": "application/json",
}


class YahooFinanceProvider(StockProvider):
    """
    Outbound adapter: fetches stock quotes from Yahoo Finance public API.

    Two-call strategy:
      1. /v8/finance/chart  — fast, gets current price + OHLCV
      2. /v10/finance/quoteSummary — gets market cap, PE ratio, 52-week range

    No API key required. Vietnamese stocks need the '.VN' suffix
    (e.g. HPG.VN, VCB.VN, FPT.VN).
    """

    def __init__(self, timeout: int = 10) -> None:
        self._timeout = timeout

    async def get_quote(self, symbol: str) -> Optional[StockQuote]:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=self._timeout) as client:
            quote = await self._fetch_chart(client, symbol)
            if quote is None:
                return None
            extra = await self._fetch_summary(client, symbol)
        return _merge(quote, extra)

    async def _fetch_chart(
        self, client: httpx.AsyncClient, symbol: str
    ) -> Optional[StockQuote]:
        try:
            resp = await client.get(_CHART_URL.format(symbol=symbol))
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("YahooChart HTTP %s for %s", exc.response.status_code, symbol)
            return None
        except Exception as exc:
            logger.error("YahooChart error for %s: %s", symbol, exc)
            return None

        result = data.get("chart", {}).get("result") or []
        if not result:
            logger.warning("YahooChart: no result for %s", symbol)
            return None

        meta: dict[str, Any] = result[0].get("meta", {})
        price = _float(meta.get("regularMarketPrice"))
        if price is None:
            return None

        prev_close = _float(meta.get("chartPreviousClose") or meta.get("previousClose")) or price

        return StockQuote(
            symbol=meta.get("symbol") or symbol,
            price=price,
            open=_float(meta.get("regularMarketOpen")) or price,
            high=_float(meta.get("regularMarketDayHigh")) or price,
            low=_float(meta.get("regularMarketDayLow")) or price,
            volume=int(meta.get("regularMarketVolume") or 0),
            previous_close=prev_close,
            currency=meta.get("currency") or "USD",
            exchange=meta.get("exchangeName") or "",
            company_name=meta.get("longName") or meta.get("shortName") or symbol,
            fetched_at=datetime.utcnow(),
        )

    async def _fetch_summary(
        self, client: httpx.AsyncClient, symbol: str
    ) -> dict[str, Any]:
        """Fetch extended fundamentals. Returns empty dict on any failure."""
        try:
            resp = await client.get(_SUMMARY_URL.format(symbol=symbol))
            resp.raise_for_status()
            data = resp.json()
            result = data.get("quoteSummary", {}).get("result") or []
            if not result:
                return {}
            modules: dict[str, Any] = result[0]
            price_mod: dict[str, Any] = modules.get("price") or {}
            detail_mod: dict[str, Any] = modules.get("summaryDetail") or {}
            stats_mod: dict[str, Any] = modules.get("defaultKeyStatistics") or {}
            return {
                "market_cap": _raw(price_mod.get("marketCap")),
                "pe_ratio": _raw(detail_mod.get("trailingPE")),
                "week_52_high": _raw(detail_mod.get("fiftyTwoWeekHigh")),
                "week_52_low": _raw(detail_mod.get("fiftyTwoWeekLow")),
            }
        except Exception as exc:
            logger.debug("YahooSummary skipped for %s: %s", symbol, exc)
            return {}

    async def is_healthy(self) -> bool:
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=5) as client:
                resp = await client.get(_CHART_URL.format(symbol="AAPL"))
                return resp.status_code == 200
        except Exception:
            return False


# ── helpers ─────────────────────────────────────────────────────────────────

def _float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _raw(value: Any) -> Optional[float]:
    """Extract numeric from Yahoo's {raw: X, fmt: '...'} wrapper or plain float."""
    if isinstance(value, dict):
        return _float(value.get("raw"))
    return _float(value)


def _merge(base: StockQuote, extra: dict[str, Any]) -> StockQuote:
    """Return a new StockQuote with extended fields filled in from summary."""
    return StockQuote(
        symbol=base.symbol,
        price=base.price,
        open=base.open,
        high=base.high,
        low=base.low,
        volume=base.volume,
        previous_close=base.previous_close,
        currency=base.currency,
        exchange=base.exchange,
        company_name=base.company_name,
        fetched_at=base.fetched_at,
        market_cap=extra.get("market_cap"),
        pe_ratio=extra.get("pe_ratio"),
        week_52_high=extra.get("week_52_high"),
        week_52_low=extra.get("week_52_low"),
    )
