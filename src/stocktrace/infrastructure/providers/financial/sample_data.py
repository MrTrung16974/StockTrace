"""Sample financial data for development and testing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from stocktrace.domain.entities.financial import (
    BalanceSheet,
    CashFlow,
    CompanyFundamental,
    IncomeStatement,
    RevenueSegment,
)

_BILLION = Decimal("1000000000")

_COMPANY_DATA: dict[str, dict] = {
    "FPT": {
        "name": "FPT CORPORATION",
        "sector": "Technology",
        "industry": "IT Services",
        "market_cap": Decimal("150000") * _BILLION,
        "shares": Decimal("1700000000"),
        "segments": (
            RevenueSegment("Technology", Decimal("62")),
            RevenueSegment("Telecom", Decimal("23")),
            RevenueSegment("Education", Decimal("10")),
            RevenueSegment("Other", Decimal("5")),
        ),
        "quarters": [
            ("Q1", date(2025, 3, 31), Decimal("14000"), Decimal("2200"), Decimal("1000")),
            ("Q2", date(2025, 6, 30), Decimal("15200"), Decimal("2400"), Decimal("1200")),
            ("Q3", date(2025, 9, 30), Decimal("16500"), Decimal("2600"), Decimal("1500")),
            ("Q4", date(2025, 12, 31), Decimal("17800"), Decimal("2900"), Decimal("1800")),
        ],
    },
    "VCB": {
        "name": "VIETCOMBANK",
        "sector": "Financials",
        "industry": "Banking",
        "market_cap": Decimal("400000") * _BILLION,
        "shares": Decimal("8350000000"),
        "segments": (
            RevenueSegment("Interest Income", Decimal("70")),
            RevenueSegment("Fee Income", Decimal("20")),
            RevenueSegment("Other", Decimal("10")),
        ),
        "quarters": [
            ("Q1", date(2025, 3, 31), Decimal("25000"), Decimal("8000"), Decimal("2000")),
            ("Q2", date(2025, 6, 30), Decimal("26500"), Decimal("8500"), Decimal("2200")),
            ("Q3", date(2025, 9, 30), Decimal("28000"), Decimal("9000"), Decimal("2400")),
            ("Q4", date(2025, 12, 31), Decimal("29500"), Decimal("9500"), Decimal("2600")),
        ],
    },
    "CMG": {
        "name": "CMG CORPORATION",
        "sector": "Technology",
        "industry": "IT Distribution",
        "market_cap": Decimal("8000") * _BILLION,
        "shares": Decimal("200000000"),
        "segments": (
            RevenueSegment("Distribution", Decimal("55")),
            RevenueSegment("Services", Decimal("30")),
            RevenueSegment("Other", Decimal("15")),
        ),
        "quarters": [
            ("Q1", date(2025, 3, 31), Decimal("3200"), Decimal("400"), Decimal("200")),
            ("Q2", date(2025, 6, 30), Decimal("3400"), Decimal("420"), Decimal("220")),
            ("Q3", date(2025, 9, 30), Decimal("3600"), Decimal("450"), Decimal("250")),
            ("Q4", date(2025, 12, 31), Decimal("3800"), Decimal("480"), Decimal("280")),
        ],
    },
    "HPG": {
        "name": "HOA PHAT GROUP",
        "sector": "Materials",
        "industry": "Steel",
        "market_cap": Decimal("180000") * _BILLION,
        "shares": Decimal("6400000000"),
        "segments": (
            RevenueSegment("Steel", Decimal("84")),
            RevenueSegment("Agriculture", Decimal("9")),
            RevenueSegment("Real Estate", Decimal("5")),
            RevenueSegment("Other", Decimal("2")),
        ),
        "quarters": [
            ("Q1", date(2025, 3, 31), Decimal("31000"), Decimal("3300"), Decimal("3900")),
            ("Q2", date(2025, 6, 30), Decimal("33500"), Decimal("3600"), Decimal("4200")),
            ("Q3", date(2025, 9, 30), Decimal("35200"), Decimal("3900"), Decimal("4500")),
            ("Q4", date(2025, 12, 31), Decimal("37800"), Decimal("4300"), Decimal("5100")),
        ],
    },
}

_HISTORICAL_PE: dict[str, list[tuple[int, Decimal]]] = {
    "FPT": [
        (2021, Decimal("15")),
        (2022, Decimal("17")),
        (2023, Decimal("21")),
        (2024, Decimal("23")),
        (2025, Decimal("19.2")),
    ],
    "VCB": [
        (2021, Decimal("12")),
        (2022, Decimal("14")),
        (2023, Decimal("16")),
        (2024, Decimal("18")),
        (2025, Decimal("15.5")),
    ],
    "CMG": [
        (2021, Decimal("18")),
        (2022, Decimal("20")),
        (2023, Decimal("22")),
        (2024, Decimal("25")),
        (2025, Decimal("21")),
    ],
    "HPG": [
        (2021, Decimal("11")),
        (2022, Decimal("9")),
        (2023, Decimal("14")),
        (2024, Decimal("17")),
        (2025, Decimal("12.8")),
    ],
}


def get_company_data(symbol: str) -> dict | None:
    """Return sample company data for a symbol."""
    return _COMPANY_DATA.get(symbol.upper())


def build_income_statement(
    symbol: str,
    period: str,
    period_end: date,
    revenue_b: Decimal,
    profit_b: Decimal,
    ocf_b: Decimal,
) -> IncomeStatement:
    """Build a sample income statement."""
    revenue = revenue_b * _BILLION
    cogs = revenue * Decimal("0.55")
    gross = revenue - cogs
    opex = revenue * Decimal("0.25")
    operating = gross - opex
    ebitda = operating * Decimal("1.15")
    net = profit_b * _BILLION
    shares = _COMPANY_DATA.get(symbol, {}).get("shares", Decimal("1000000000"))
    eps = net / shares

    return IncomeStatement(
        symbol=symbol,
        period=period,
        period_end=period_end,
        revenue=revenue,
        cost_of_goods=cogs,
        gross_profit=gross,
        operating_expenses=opex,
        operating_income=operating,
        ebitda=ebitda,
        net_income=net,
        eps=eps,
    )


def build_balance_sheet(
    symbol: str,
    period: str,
    period_end: date,
    revenue_b: Decimal,
) -> BalanceSheet:
    """Build a sample balance sheet."""
    assets = revenue_b * _BILLION * Decimal("3")
    equity = assets * Decimal("0.45")
    liabilities = assets - equity
    st_debt = liabilities * Decimal("0.3")
    lt_debt = liabilities * Decimal("0.4")
    cash = assets * Decimal("0.1")
    inventory = assets * Decimal("0.08")
    current_assets = assets * Decimal("0.35")
    current_liabilities = liabilities * Decimal("0.4")

    return BalanceSheet(
        symbol=symbol,
        period=period,
        period_end=period_end,
        total_assets=assets,
        total_liabilities=liabilities,
        total_equity=equity,
        short_term_debt=st_debt,
        long_term_debt=lt_debt,
        cash_and_equivalents=cash,
        inventory=inventory,
        current_assets=current_assets,
        current_liabilities=current_liabilities,
    )


def build_cash_flow(
    symbol: str,
    period: str,
    period_end: date,
    ocf_b: Decimal,
    profit_b: Decimal,
) -> CashFlow:
    """Build a sample cash flow statement."""
    ocf = ocf_b * _BILLION
    capex = ocf * Decimal("0.3")
    fcf = ocf - capex

    return CashFlow(
        symbol=symbol,
        period=period,
        period_end=period_end,
        operating_cash_flow=ocf,
        investing_cash_flow=-capex,
        financing_cash_flow=-fcf * Decimal("0.2"),
        free_cash_flow=fcf,
        capex=capex,
    )


def build_fundamentals(symbol: str) -> CompanyFundamental | None:
    """Build company fundamentals from sample data."""
    data = get_company_data(symbol)
    if data is None:
        return None
    return CompanyFundamental(
        symbol=symbol,
        company_name=data["name"],
        sector=data["sector"],
        industry=data["industry"],
        market_cap=data["market_cap"],
        shares_outstanding=data["shares"],
        revenue_segments=data["segments"],
        data_source="Dữ liệu mô phỏng nội bộ",
        is_mock_data=True,
    )
