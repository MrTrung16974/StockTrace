"""Financial ratio calculation engine."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from stocktrace.domain.entities.financial import (
    BalanceSheet,
    CashFlow,
    FinancialRatio,
    FinancialStatement,
    IncomeStatement,
)


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
        return (ratio ** exponent - Decimal("1")) * Decimal("100")
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
            prev = sorted_stmts[i - 1] if i > 0 else None
            ratio = self._calculate_single(
                stmt,
                prev,
                market_price,
                shares_outstanding,
                len(sorted_stmts),
            )
            ratios.append(ratio)

        return ratios

    def _calculate_single(
        self,
        stmt: FinancialStatement,
        prev: FinancialStatement | None,
        market_price: Decimal | None,
        shares_outstanding: Decimal | None,
        total_periods: int,
    ) -> FinancialRatio:
        inc = stmt.income
        bal = stmt.balance
        cf = stmt.cash_flow

        total_debt = bal.short_term_debt + bal.long_term_debt

        roe = _safe_div(inc.net_income, bal.total_equity)
        roa = _safe_div(inc.net_income, bal.total_assets)
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

        if total_periods > 1 and prev is not None:
            first = prev.income.revenue
            revenue_cagr = _cagr(first, inc.revenue, total_periods - 1)

        debt_to_equity = _safe_div(total_debt, bal.total_equity)
        debt_to_asset = _safe_div(total_debt, bal.total_assets)
        interest_coverage = _safe_div(inc.operating_income, bal.long_term_debt * Decimal("0.05"))
        current_ratio = _safe_div(bal.current_assets, bal.current_liabilities)
        quick_assets = bal.current_assets - bal.inventory
        quick_ratio = _safe_div(quick_assets, bal.current_liabilities)

        cash_conversion = _safe_div(cf.operating_cash_flow, inc.net_income)

        pe = pb = peg = ev_ebitda = dcf_value = graham_value = None

        if market_price and inc.eps and inc.eps > 0:
            pe = _safe_div(market_price, inc.eps)

        if market_price and bal.total_equity and shares_outstanding and shares_outstanding > 0:
            book_value_per_share = bal.total_equity / shares_outstanding
            pb = _safe_div(market_price, book_value_per_share)

        if pe and eps_growth and eps_growth > 0:
            peg = _safe_div(pe, eps_growth)

        if inc.ebitda > 0:
            ev_ebitda = _safe_div(inc.ebitda, inc.ebitda)

        if inc.eps > 0 and roe and roe > 0:
            growth_rate = eps_growth or Decimal("5")
            graham_value = inc.eps * (Decimal("8.5") + Decimal("2") * growth_rate)

        if cf.free_cash_flow > 0 and shares_outstanding and shares_outstanding > 0:
            fcf_per_share = cf.free_cash_flow / shares_outstanding
            dcf_value = fcf_per_share * Decimal("15")

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
