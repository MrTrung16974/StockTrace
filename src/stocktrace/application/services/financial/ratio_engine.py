"""Financial ratio calculation engine."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from stocktrace.domain.entities.financial import (
    CashFlow,
    FinancialRatio,
    FinancialStatement,
    IncomeStatement,
)

_QUARTERS_PER_YEAR = 4
_MIN_TTM_INDEX = _QUARTERS_PER_YEAR - 1


def _safe_div(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    """Safely divide two decimals, returning None on zero/invalid."""
    if denominator == 0:
        return None
    try:
        return numerator / denominator
    except (InvalidOperation, ZeroDivisionError):
        return None


def _pct_change(current: Decimal, previous: Decimal) -> Decimal | None:
    """Calculate percentage change."""
    if previous == 0:
        return None
    return ((current - previous) / abs(previous)) * Decimal("100")


def _cagr(start: Decimal, end: Decimal, periods: int) -> Decimal | None:
    """Calculate compound annual growth rate."""
    if start <= 0 or periods <= 0:
        return None
    try:
        ratio = end / start
        exponent = Decimal("1") / Decimal(str(periods))
        return (ratio**exponent - Decimal("1")) * Decimal("100")
    except (InvalidOperation, ZeroDivisionError):
        return None


class FinancialRatioEngine:
    """Pure calculation engine for financial ratios."""

    def calculate(
        self,
        statements: list[FinancialStatement],
        market_price: Decimal | None = None,
        shares_outstanding: Decimal | None = None,
    ) -> list[FinancialRatio]:
        """Calculate ratios for each statement period."""
        if not statements:
            return []

        sorted_stmts = sorted(statements, key=lambda s: s.period_end)
        ratios: list[FinancialRatio] = []

        for i, stmt in enumerate(sorted_stmts):
            current = _ttm_statement(sorted_stmts, i) or stmt
            # For quarterly statements, growth must compare the same quarter/TTM
            # window one year earlier, not the immediately preceding quarter.
            if _is_quarterly(stmt):
                prev = (
                    _ttm_statement(sorted_stmts, i - _QUARTERS_PER_YEAR)
                    if i >= _QUARTERS_PER_YEAR
                    else None
                )
            else:
                prev = sorted_stmts[i - 1] if i > 0 else None
            ratio = _calculate_single(
                current,
                prev,
                sorted_stmts[0],
                market_price,
                shares_outstanding,
                len(sorted_stmts),
            )
            ratios.append(ratio)

        return ratios


def _is_quarterly(statement: FinancialStatement) -> bool:
    return statement.period.upper().startswith("Q")


def _ttm_statement(
    statements: list[FinancialStatement],
    index: int,
) -> FinancialStatement | None:
    """Build a trailing-twelve-month statement from four quarterly observations."""
    if index < _MIN_TTM_INDEX:
        return None

    window = statements[index - _MIN_TTM_INDEX : index + 1]
    if len(window) != _QUARTERS_PER_YEAR or not all(
        _is_quarterly(statement) for statement in window
    ):
        return None

    latest = window[-1]
    income = IncomeStatement(
        symbol=latest.symbol,
        period="TTM",
        period_end=latest.period_end,
        revenue=sum((item.income.revenue for item in window), Decimal("0")),
        cost_of_goods=sum((item.income.cost_of_goods for item in window), Decimal("0")),
        gross_profit=sum((item.income.gross_profit for item in window), Decimal("0")),
        operating_expenses=sum((item.income.operating_expenses for item in window), Decimal("0")),
        operating_income=sum((item.income.operating_income for item in window), Decimal("0")),
        ebitda=sum((item.income.ebitda for item in window), Decimal("0")),
        net_income=sum((item.income.net_income for item in window), Decimal("0")),
        eps=sum((item.income.eps for item in window), Decimal("0")),
        currency=latest.income.currency,
    )
    cash_flow = CashFlow(
        symbol=latest.symbol,
        period="TTM",
        period_end=latest.period_end,
        operating_cash_flow=sum(
            (item.cash_flow.operating_cash_flow for item in window), Decimal("0")
        ),
        investing_cash_flow=sum(
            (item.cash_flow.investing_cash_flow for item in window), Decimal("0")
        ),
        financing_cash_flow=sum(
            (item.cash_flow.financing_cash_flow for item in window), Decimal("0")
        ),
        free_cash_flow=sum((item.cash_flow.free_cash_flow for item in window), Decimal("0")),
        capex=sum((item.cash_flow.capex for item in window), Decimal("0")),
        currency=latest.cash_flow.currency,
    )
    return FinancialStatement(
        symbol=latest.symbol,
        period="TTM",
        period_end=latest.period_end,
        income=income,
        balance=latest.balance,
        cash_flow=cash_flow,
    )


def _average(current: Decimal, previous: Decimal | None) -> Decimal:
    """Return the average balance when a comparable opening balance exists."""
    if previous is None:
        return current
    return (current + previous) / Decimal("2")


def _calculate_single(  # noqa: PLR0915
    stmt: FinancialStatement,
    prev: FinancialStatement | None,
    first: FinancialStatement,
    market_price: Decimal | None,
    shares_outstanding: Decimal | None,
    total_periods: int,
) -> FinancialRatio:
    inc = stmt.income
    bal = stmt.balance
    cf = stmt.cash_flow

    total_debt = bal.short_term_debt + bal.long_term_debt

    # Quarterly reports require trailing-twelve-month (TTM) flows before they can
    # be compared with balance-sheet snapshots or a current market price.  The
    # caller supplies only one previous statement, so use the current period's
    # values until four quarterly reports are available.
    roe = _safe_div(
        inc.net_income,
        _average(bal.total_equity, prev.balance.total_equity if prev else None),
    )
    roa = _safe_div(
        inc.net_income,
        _average(bal.total_assets, prev.balance.total_assets if prev else None),
    )
    ros = _safe_div(inc.net_income, inc.revenue)
    gross_margin = _safe_div(inc.gross_profit, inc.revenue)
    ebitda_margin = _safe_div(inc.ebitda, inc.revenue)
    net_margin = _safe_div(inc.net_income, inc.revenue)

    revenue_growth = None
    profit_growth = None
    eps_growth = None
    revenue_cagr = None
    fcf_growth = None

    if prev is not None:
        revenue_growth = _pct_change(inc.revenue, prev.income.revenue)
        profit_growth = _pct_change(inc.net_income, prev.income.net_income)
        eps_growth = _pct_change(inc.eps, prev.income.eps)
        fcf_growth = _pct_change(cf.free_cash_flow, prev.cash_flow.free_cash_flow)

    # CAGR is meaningful only for annual observations. Period labels such as Q1
    # and Q2 are quarterly data and must not be annualised by exponent alone.
    if (
        total_periods > 1
        and prev is not None
        and not stmt.period.upper().startswith("Q")
        and stmt.period.upper() != "TTM"
    ):
        revenue_cagr = _cagr(first.income.revenue, inc.revenue, total_periods - 1)

    debt_to_equity = _safe_div(total_debt, bal.total_equity)
    debt_to_asset = _safe_div(total_debt, bal.total_assets)
    # Interest expense is not available in the normalized model. Do not invent
    # it from an assumed interest rate.
    interest_coverage = None
    current_ratio = _safe_div(bal.current_assets, bal.current_liabilities)
    quick_assets = bal.current_assets - bal.inventory
    quick_ratio = _safe_div(quick_assets, bal.current_liabilities)

    cash_conversion = _safe_div(cf.operating_cash_flow, inc.net_income)

    pe = pb = peg = ev_ebitda = dcf_value = graham_value = None

    if market_price and inc.eps and inc.eps > 0 and not stmt.period.upper().startswith("Q"):
        pe = _safe_div(market_price, inc.eps)

    if (
        market_price
        and bal.total_equity
        and shares_outstanding
        and shares_outstanding > 0
        and not stmt.period.upper().startswith("Q")
    ):
        book_value_per_share = bal.total_equity / shares_outstanding
        pb = _safe_div(market_price, book_value_per_share)

    if pe and eps_growth and eps_growth > 0:
        peg = _safe_div(pe, eps_growth)

    if (
        market_price
        and shares_outstanding
        and shares_outstanding > 0
        and inc.ebitda > 0
        and not stmt.period.upper().startswith("Q")
    ):
        enterprise_value = market_price * shares_outstanding + total_debt - bal.cash_and_equivalents
        ev_ebitda = _safe_div(enterprise_value, inc.ebitda)

    # A discounted-cash-flow valuation needs explicit forecast, discount-rate and
    # terminal-value assumptions. Graham valuation also needs normalized annual
    # EPS and a defensible long-term growth assumption. Leave both unavailable
    # rather than presenting hard-coded multiples as intrinsic value.

    if roe:
        roe = roe * Decimal("100")
    if roa:
        roa = roa * Decimal("100")
    if ros:
        ros = ros * Decimal("100")
    if gross_margin:
        gross_margin = gross_margin * Decimal("100")
    if ebitda_margin:
        ebitda_margin = ebitda_margin * Decimal("100")
    if net_margin:
        net_margin = net_margin * Decimal("100")

    return FinancialRatio(
        symbol=stmt.symbol,
        period=stmt.period,
        period_end=stmt.period_end,
        roe=roe,
        roa=roa,
        ros=ros,
        gross_margin=gross_margin,
        ebitda_margin=ebitda_margin,
        net_margin=net_margin,
        revenue_growth=revenue_growth,
        profit_growth=profit_growth,
        eps_growth=eps_growth,
        revenue_cagr=revenue_cagr,
        debt_to_equity=debt_to_equity,
        debt_to_asset=debt_to_asset,
        interest_coverage=interest_coverage,
        current_ratio=current_ratio,
        quick_ratio=quick_ratio,
        operating_cash_flow=cf.operating_cash_flow,
        free_cash_flow=cf.free_cash_flow,
        fcf_growth=fcf_growth,
        cash_conversion=cash_conversion,
        pe=pe,
        pb=pb,
        peg=peg,
        ev_ebitda=ev_ebitda,
        dcf_value=dcf_value,
        graham_value=graham_value,
    )
