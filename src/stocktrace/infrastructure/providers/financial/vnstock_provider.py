"""Vnstock adapter for public Vietnamese financial statements."""

from __future__ import annotations

import asyncio
import math
import re
from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from vnstock import Finance

from stocktrace.domain.entities.financial import (
    BalanceSheet,
    CashFlow,
    CompanyFundamental,
    FinancialProfile,
    FinancialRatio,
    IncomeStatement,
)
from stocktrace.domain.ports.financial_provider import (
    FinancialDataNotFoundError,
    FinancialProviderError,
)
from stocktrace.domain.value_objects.financial_period import FinancialPeriod, PeriodUnit
from stocktrace.infrastructure.logging.config import get_logger

logger = get_logger(__name__)

_PERIOD_PATTERN = re.compile(r"^(?P<year>\d{4})-Q(?P<quarter>[1-4])")
_ANNUAL_PERIOD_PATTERN = re.compile(r"^(?P<year>\d{4})$")
_INCOME_IDS = {
    "revenue": ("revenue", "net_revenue", "total_operating_income"),
    "cost_of_goods": ("cost_of_goods_sold", "cost_of_sales"),
    "gross_profit": ("gross_profit",),
    "operating_expenses": ("selling_expenses", "general_and_admin_expenses"),
    "operating_income": (
        "operating_profit_loss",
        "operating_income",
        "net_operating_profit_before_allowance_for_credit_loss",
    ),
    "net_income": ("attributable_to_parent_company", "net_profit_loss_after_tax"),
    "eps": ("eps_basic_vnd",),
}
_BALANCE_IDS = {
    "total_assets": ("total_assets",),
    "total_liabilities": ("total_liabilities",),
    "total_equity": ("owners_equity", "total_equity"),
    "cash": ("cash_and_cash_equivalents", "cash_and_precious_metals"),
    "inventory": ("inventories", "inventory"),
    "current_assets": ("current_assets",),
    "current_liabilities": ("current_liabilities",),
    "short_term_debt": ("short_term_borrowings", "short_term_debt"),
    "long_term_debt": ("long_term_borrowings", "long_term_debt"),
}
_CASH_FLOW_IDS = {
    "operating": ("net_cash_from_operating_activities",),
    "investing": ("net_cash_from_investing_activities",),
    "financing": ("net_cash_from_financing_activities",),
    "capex": ("purchases_of_fixed_assets_and_other_long_term_assets",),
}


class VNStockFinancialProvider:
    """Retrieve public financial statements through Vnstock's VCI adapter."""

    def __init__(self, api_key: str | None = None, timeout_seconds: float = 30.0) -> None:
        self._api_key = api_key
        self._timeout = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "vnstock-vci"

    async def get_income_statement(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[IncomeStatement]:
        frame = await self._fetch_statement(symbol, "income_statement", period)
        rows = _statement_rows(frame, period)
        statements: list[IncomeStatement] = []
        for label, period_end, values in rows:
            revenue = _value(values, _INCOME_IDS["revenue"])
            net_income = _value(values, _INCOME_IDS["net_income"])
            if revenue is None or net_income is None:
                continue
            cost_of_goods = _value(values, _INCOME_IDS["cost_of_goods"]) or Decimal("0")
            gross_profit = _value(values, _INCOME_IDS["gross_profit"]) or revenue - cost_of_goods
            operating_expenses = _sum_values(values, _INCOME_IDS["operating_expenses"])
            operating_income = _value(values, _INCOME_IDS["operating_income"]) or net_income
            statements.append(
                IncomeStatement(
                    symbol=symbol,
                    period=label,
                    period_end=period_end,
                    revenue=revenue,
                    cost_of_goods=cost_of_goods,
                    gross_profit=gross_profit,
                    operating_expenses=operating_expenses,
                    operating_income=operating_income,
                    ebitda=operating_income,
                    net_income=net_income,
                    eps=_value(values, _INCOME_IDS["eps"]) or Decimal("0"),
                    profile=(
                        FinancialProfile.BANK
                        if "net_interest_income" in values
                        else FinancialProfile.GENERAL
                    ),
                ),
            )
        return _require_data(symbol, statements, "báo cáo kết quả kinh doanh")

    async def get_balance_sheet(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[BalanceSheet]:
        frame = await self._fetch_statement(symbol, "balance_sheet", period)
        rows = _statement_rows(frame, period)
        statements: list[BalanceSheet] = []
        for label, period_end, values in rows:
            assets = _value(values, _BALANCE_IDS["total_assets"])
            liabilities = _value(values, _BALANCE_IDS["total_liabilities"])
            equity = _value(values, _BALANCE_IDS["total_equity"])
            if assets is None or liabilities is None or equity is None:
                continue
            statements.append(
                BalanceSheet(
                    symbol=symbol,
                    period=label,
                    period_end=period_end,
                    total_assets=assets,
                    total_liabilities=liabilities,
                    total_equity=equity,
                    short_term_debt=_value(values, _BALANCE_IDS["short_term_debt"]) or Decimal("0"),
                    long_term_debt=_value(values, _BALANCE_IDS["long_term_debt"]) or Decimal("0"),
                    cash_and_equivalents=_value(values, _BALANCE_IDS["cash"]) or Decimal("0"),
                    inventory=_value(values, _BALANCE_IDS["inventory"]) or Decimal("0"),
                    current_assets=_value(values, _BALANCE_IDS["current_assets"]) or Decimal("0"),
                    current_liabilities=_value(values, _BALANCE_IDS["current_liabilities"])
                    or Decimal("0"),
                ),
            )
        return _require_data(symbol, statements, "bảng cân đối kế toán")

    async def get_cash_flow(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[CashFlow]:
        frame = await self._fetch_statement(symbol, "cash_flow", period)
        rows = _statement_rows(frame, period)
        statements: list[CashFlow] = []
        for label, period_end, values in rows:
            operating = _value(values, _CASH_FLOW_IDS["operating"])
            if operating is None:
                continue
            capex = abs(_value(values, _CASH_FLOW_IDS["capex"]) or Decimal("0"))
            statements.append(
                CashFlow(
                    symbol=symbol,
                    period=label,
                    period_end=period_end,
                    operating_cash_flow=operating,
                    investing_cash_flow=_value(values, _CASH_FLOW_IDS["investing"]) or Decimal("0"),
                    financing_cash_flow=_value(values, _CASH_FLOW_IDS["financing"]) or Decimal("0"),
                    free_cash_flow=operating - capex,
                    capex=capex,
                ),
            )
        return _require_data(symbol, statements, "báo cáo lưu chuyển tiền tệ")

    async def get_ratios(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[FinancialRatio]:
        return []

    async def get_company_fundamentals(self, symbol: str) -> CompanyFundamental:
        return CompanyFundamental(
            symbol=symbol,
            company_name=symbol,
            sector="Chưa phân loại",
            industry="Chưa phân loại",
            data_source="Vnstock / VCI (dữ liệu công khai)",
        )

    async def _fetch_statement(
        self,
        symbol: str,
        method_name: str,
        period: FinancialPeriod,
    ) -> Any:
        """Call Vnstock in a worker thread because its client is synchronous."""

        def fetch() -> Any:
            finance = Finance(source="vci", symbol=symbol, show_log=False)
            return getattr(finance, method_name)(period=_source_period(period))

        try:
            return await asyncio.wait_for(asyncio.to_thread(fetch), timeout=self._timeout)
        except TimeoutError as exc:
            raise FinancialProviderError("Hết thời gian chờ dữ liệu báo cáo tài chính.") from exc
        except FinancialProviderError:
            raise
        except Exception as exc:
            logger.warning("vnstock_financial_fetch_failed", symbol=symbol, error=str(exc))
            raise FinancialProviderError("Không thể tải báo cáo tài chính từ Vnstock.") from exc


def _statement_rows(
    frame: Any, period: FinancialPeriod
) -> list[tuple[str, date, dict[str, Decimal]]]:
    """Convert Vnstock's pivoted frame to chronological period records."""
    if getattr(frame, "empty", True) or "item_id" not in frame.columns:
        return []

    records: list[tuple[str, date, dict[str, Decimal]]] = []
    for column in frame.columns:
        parsed = _parse_period(str(column))
        if parsed is None:
            continue
        label, period_end = parsed
        values: dict[str, Decimal] = {}
        for _, row in frame.iterrows():
            item_id = row.get("item_id")
            value = _decimal(row.get(column))
            if isinstance(item_id, str) and value is not None:
                values[item_id] = value
        records.append((label, period_end, values))

    requested = (
        period.value
        if period.unit == PeriodUnit.YEAR and period.value > 1
        else max(1, math.ceil(period.months / 3))
    )
    return sorted(records, key=lambda item: item[1])[-requested:]


def _parse_period(value: str) -> tuple[str, date] | None:
    match = _PERIOD_PATTERN.match(value)
    if match is not None:
        year = int(match.group("year"))
        quarter = int(match.group("quarter"))
        month = quarter * 3
        return f"Q{quarter}", date(year, month, monthrange(year, month)[1])

    annual_match = _ANNUAL_PERIOD_PATTERN.match(value)
    if annual_match is None:
        return None
    year = int(annual_match.group("year"))
    return f"FY{year}", date(year, 12, 31)


def _source_period(period: FinancialPeriod) -> str:
    """Select annual history for multi-year analysis; otherwise use quarters for TTM."""
    if period.unit == PeriodUnit.YEAR and period.value > 1:
        return "year"
    return "quarter"


def _decimal(value: object) -> Decimal | None:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _value(values: dict[str, Decimal], item_ids: tuple[str, ...]) -> Decimal | None:
    for item_id in item_ids:
        if item_id in values:
            return values[item_id]
    return None


def _sum_values(values: dict[str, Decimal], item_ids: tuple[str, ...]) -> Decimal:
    return sum((values[item_id] for item_id in item_ids if item_id in values), Decimal("0"))


def _require_data[T](symbol: str, values: list[T], statement_name: str) -> list[T]:
    if values:
        return values
    raise FinancialDataNotFoundError(f"Không có {statement_name} cho mã {symbol}.")
