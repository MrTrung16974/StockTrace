"""Yahoo Finance quote provider."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar, cast
from zoneinfo import ZoneInfo

import httpx

from stocktrace.application.services.market_data import (
    MarketDataError,
    QuoteNotFoundError,
    StockQuote,
)

HTTP_TOO_MANY_REQUESTS = 429
HTTP_NOT_FOUND = 404
HTTP_UNPROCESSABLE_ENTITY = 422
MIN_VN_SYMBOL_LENGTH = 2
MAX_VN_SYMBOL_LENGTH = 4


class YahooFinanceQuoteProvider:
    """Retrieve latest stock quotes from Yahoo Finance chart data."""

    _base_url = "https://query1.finance.yahoo.com/v8/finance/chart"
    _vndirect_stock_prices_url = "https://api-finfo.vndirect.com.vn/v4/stock_prices"
    _vndirect_stocks_url = "https://api-finfo.vndirect.com.vn/v4/stocks"
    _headers: ClassVar[dict[str, str]] = {
        "Accept": "application/json",
        "User-Agent": "StockTrace/0.1",
    }

    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds

    async def get_quote(self, symbol: str) -> StockQuote:
        """Return the latest quote for a symbol."""
        errors: list[str] = []
        for candidate in _candidate_symbols(symbol):
            try:
                return await self._get_quote_for_candidate(candidate, requested_symbol=symbol)
            except QuoteNotFoundError as exc:
                errors.append(str(exc))
            except MarketDataError as exc:
                errors.append(str(exc))

        if _looks_like_vietnam_symbol(symbol):
            try:
                return await self._get_vndirect_quote(symbol)
            except QuoteNotFoundError as exc:
                errors.append(str(exc))
            except MarketDataError as exc:
                errors.append(str(exc))

        if any("rate-limited" in error for error in errors):
            raise MarketDataError("Price provider is rate-limited. Please try again later.")
        raise QuoteNotFoundError(f"No price found for {symbol}.")

    async def _get_quote_for_candidate(self, symbol: str, requested_symbol: str) -> StockQuote:
        """Return the latest quote for a concrete provider symbol."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(
                    f"{self._base_url}/{symbol}",
                    params={"range": "1d", "interval": "1m"},
                    headers=self._headers,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == HTTP_TOO_MANY_REQUESTS:
                raise MarketDataError(f"Price provider is rate-limited for {symbol}.") from exc
            if exc.response.status_code in {HTTP_NOT_FOUND, HTTP_UNPROCESSABLE_ENTITY}:
                raise QuoteNotFoundError(f"No price found for {symbol}.") from exc
            msg = f"Could not retrieve price for {requested_symbol}."
            raise MarketDataError(msg) from exc
        except httpx.HTTPError as exc:
            msg = f"Could not retrieve price for {requested_symbol}."
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
        if previous_close != Decimal("0"):
            change_percent = (change / previous_close) * Decimal("100")
        else:
            change_percent = Decimal("0")

        timestamp = _datetime_from_timestamp(
            metadata.get("regularMarketTime"),
        ) or datetime.now(tz=UTC)
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

    async def get_historical_prices(self, symbol: str, days: int = 365) -> list[HistoricalPrice]:
        """Return historical prices for a symbol."""
        from stocktrace.application.services.market_data import HistoricalPrice
        if _looks_like_vietnam_symbol(symbol):
            normalized = symbol.strip().upper()
            try:
                async with httpx.AsyncClient(timeout=self._timeout_seconds, headers=self._headers) as client:
                    response = await client.get(
                        self._vndirect_stock_prices_url,
                        params={"sort": "date:desc", "q": f"code:{normalized}", "size": days, "page": 1},
                    )
                    response.raise_for_status()
                    data = response.json().get("data", [])
                    result = []
                    for row in data:
                        date_val = _vndirect_timestamp(row) or datetime.now(tz=UTC)
                        result.append(HistoricalPrice(
                            date=date_val,
                            open=_vnd_price(row.get("open")) or Decimal("0"),
                            high=_vnd_price(row.get("high")) or Decimal("0"),
                            low=_vnd_price(row.get("low")) or Decimal("0"),
                            close=_vnd_price(row.get("close")) or Decimal("0"),
                            volume=_int_decimal(row.get("nmVolume"))
                        ))
                    return sorted(result, key=lambda x: x.date)
            except Exception:
                pass
        
        # Fallback to Yahoo
        yahoo_symbol = f"{symbol.strip().upper()}.VN" if _looks_like_vietnam_symbol(symbol) else symbol.strip().upper()
        yahoo_range = "1y" if days >= 200 else f"{days}d"
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds, headers=self._headers) as client:
                response = await client.get(
                    f"{self._base_url}/{yahoo_symbol}",
                    params={"range": yahoo_range, "interval": "1d"},
                )
                response.raise_for_status()
                payload = response.json()
                result = payload.get("chart", {}).get("result", [])
                if not result:
                    return []
                timestamps = result[0].get("timestamp", [])
                indicators = result[0].get("indicators", {}).get("quote", [{}])[0]
                opens = indicators.get("open", [])
                highs = indicators.get("high", [])
                lows = indicators.get("low", [])
                closes = indicators.get("close", [])
                volumes = indicators.get("volume", [])
                
                hist_prices = []
                for i, ts in enumerate(timestamps):
                    if closes[i] is None:
                        continue
                    dt = datetime.fromtimestamp(ts, tz=UTC)
                    hist_prices.append(HistoricalPrice(
                        date=dt,
                        open=_decimal(opens[i]) or Decimal("0"),
                        high=_decimal(highs[i]) or Decimal("0"),
                        low=_decimal(lows[i]) or Decimal("0"),
                        close=_decimal(closes[i]) or Decimal("0"),
                        volume=int(volumes[i] or 0)
                    ))
                return sorted(hist_prices, key=lambda x: x.date)
        except Exception:
            return []

    async def get_fundamental_data(self, symbol: str) -> FundamentalData:
        """Return fundamental and foreign-flow data for a symbol."""
        from stocktrace.application.services.market_data import FundamentalData

        normalized = symbol.strip().upper()
        if _looks_like_vietnam_symbol(normalized):
            data = await self._get_vndirect_fundamentals(normalized)
            if data != FundamentalData():
                return data

        return await self._get_yahoo_fundamentals(normalized)

    async def _get_vndirect_fundamentals(self, symbol: str) -> FundamentalData:
        from stocktrace.application.services.market_data import FundamentalData

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds, headers=self._headers) as client:
                ratio_response = await client.get(
                    "https://api-finfo.vndirect.com.vn/v4/ratios",
                    params={
                        "q": f"code:{symbol}",
                        "size": 1,
                        "page": 1,
                        "sort": "reportDate:desc",
                    },
                )
                ratio_response.raise_for_status()

                price_response = await client.get(
                    self._vndirect_stock_prices_url,
                    params={
                        "sort": "date:desc",
                        "q": f"code:{symbol}",
                        "size": 1,
                        "page": 1,
                    },
                )
                price_response.raise_for_status()
        except httpx.HTTPError:
            return FundamentalData()

        ratio_row = _first_optional_data_row(ratio_response.json()) or {}
        price_row = _first_optional_data_row(price_response.json()) or {}

        return FundamentalData(
            eps=_decimal(ratio_row.get("eps")),
            pe=_decimal(ratio_row.get("pe")),
            pb=_decimal(ratio_row.get("pb")),
            roe=_decimal(ratio_row.get("roe")),
            roa=_decimal(ratio_row.get("roa")),
            foreign_buy_vol=_int_optional(
                price_row.get("frBuyVol") or price_row.get("frBVol") or price_row.get("foreignBuyVolume"),
            ),
            foreign_sell_vol=_int_optional(
                price_row.get("frSellVol") or price_row.get("frSVol") or price_row.get("foreignSellVolume"),
            ),
        )

    async def _get_yahoo_fundamentals(self, symbol: str) -> FundamentalData:
        from stocktrace.application.services.market_data import FundamentalData

        yahoo_symbol = f"{symbol}.VN" if _looks_like_vietnam_symbol(symbol) else symbol
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds, headers=self._headers) as client:
                response = await client.get(
                    f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{yahoo_symbol}",
                    params={"modules": "defaultKeyStatistics,summaryDetail,financialData"},
                )
                response.raise_for_status()
        except httpx.HTTPError:
            return FundamentalData()

        payload = response.json()
        result = payload.get("quoteSummary", {}).get("result", [])
        if not result:
            return FundamentalData()

        stats = result[0].get("defaultKeyStatistics") or {}
        summary = result[0].get("summaryDetail") or {}
        financial = result[0].get("financialData") or {}

        def _raw(block: dict, key: str) -> Decimal | None:
            item = block.get(key) or {}
            return _decimal(item.get("raw") if isinstance(item, dict) else item)

        return FundamentalData(
            eps=_raw(stats, "trailingEps"),
            pe=_raw(summary, "trailingPE"),
            pb=_raw(stats, "priceToBook"),
            roe=_raw(financial, "returnOnEquity"),
            roa=_raw(financial, "returnOnAssets"),
        )

    async def _get_vndirect_quote(self, symbol: str) -> StockQuote:
        """Return a latest Vietnam stock quote from VNDIRECT public market data."""
        normalized = symbol.strip().upper()
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                headers=self._headers,
            ) as client:
                price_response = await client.get(
                    self._vndirect_stock_prices_url,
                    params={
                        "sort": "date:desc",
                        "q": f"code:{normalized}",
                        "size": 1,
                        "page": 1,
                    },
                )
                price_response.raise_for_status()

                company_response = await client.get(
                    self._vndirect_stocks_url,
                    params={
                        "fields": "code,shortName,companyNameEng",
                        "q": f"code:{normalized}",
                        "size": 1,
                    },
                )
                company_response.raise_for_status()
        except httpx.HTTPError as exc:
            msg = f"Could not retrieve price for {normalized}."
            raise MarketDataError(msg) from exc

        price_row = _first_data_row(price_response.json(), symbol=normalized)
        company_row = _first_optional_data_row(company_response.json())
        current_price = _vnd_price(price_row.get("close"))
        if current_price is None:
            raise QuoteNotFoundError(f"No price found for {normalized}.")

        reference_price = _vnd_price(price_row.get("basicPrice")) or current_price
        change = _vnd_price(price_row.get("change"))
        if change is None:
            change = current_price - reference_price

        change_percent = _decimal(price_row.get("pctChange"))
        if change_percent is None and reference_price != Decimal("0"):
            change_percent = (change / reference_price) * Decimal("100")

        return StockQuote(
            ticker=normalized,
            company_name=_company_name(company_row, fallback=normalized),
            current_price=current_price,
            change=change,
            change_percent=change_percent or Decimal("0"),
            open_price=_vnd_price(price_row.get("open")) or current_price,
            high_price=_vnd_price(price_row.get("high")) or current_price,
            low_price=_vnd_price(price_row.get("low")) or current_price,
            volume=_int_decimal(price_row.get("nmVolume")),
            timestamp=_vndirect_timestamp(price_row) or datetime.now(tz=UTC),
            currency="VND",
            source="VNDIRECT",
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


def _first_data_row(payload: object, symbol: str) -> dict[str, Any]:
    row = _first_optional_data_row(payload)
    if row is None:
        raise QuoteNotFoundError(f"No price found for {symbol}.")
    return row


def _first_optional_data_row(payload: object) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        return None
    return cast(dict[str, Any], data[0])


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


def _vndirect_timestamp(row: dict[str, Any]) -> datetime | None:
    date_value = row.get("date")
    time_value = row.get("time")
    if not isinstance(date_value, str) or not isinstance(time_value, str):
        return None
    try:
        local_time = datetime.fromisoformat(f"{date_value}T{time_value}")
    except ValueError:
        return None
    return local_time.replace(tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")).astimezone(UTC)


def _vnd_price(value: object) -> Decimal | None:
    amount = _decimal(value)
    if amount is None:
        return None
    return amount * Decimal("1000")


def _int_decimal(value: object) -> int:
    amount = _decimal(value)
    if amount is None:
        return 0
    return int(amount)


def _int_optional(value: object) -> int | None:
    if value is None:
        return None
    amount = _decimal(value)
    if amount is None:
        return None
    return int(amount)


def _company_name(row: dict[str, Any] | None, fallback: str) -> str:
    if row is None:
        return fallback
    for key in ("companyNameEng", "shortName", "companyName"):
        value = row.get(key)
        if value:
            return str(value)
    return fallback


def _looks_like_vietnam_symbol(symbol: str) -> bool:
    normalized = symbol.strip().upper()
    return (
        "." not in normalized
        and normalized.isalpha()
        and MIN_VN_SYMBOL_LENGTH <= len(normalized) <= MAX_VN_SYMBOL_LENGTH
    )


def _candidate_symbols(symbol: str) -> list[str]:
    normalized = symbol.strip().upper()
    if _looks_like_vietnam_symbol(normalized):
        return [f"{normalized}.VN", normalized]
    return [normalized]
