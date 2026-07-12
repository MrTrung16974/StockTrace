"""Financial scoring engine with weighted categories."""

from __future__ import annotations

from decimal import Decimal

from stocktrace.domain.entities.financial import (
    CategoryScore,
    FinancialProfile,
    FinancialRatio,
    FinancialScore,
    Recommendation,
    Valuation,
)

WEIGHTS = {
    "growth": Decimal("0.30"),
    "profitability": Decimal("0.25"),
    "debt": Decimal("0.15"),
    "cash_flow": Decimal("0.15"),
    "valuation": Decimal("0.15"),
}


def _clamp_score(value: Decimal) -> Decimal:
    """Clamp score to 0-100 range."""
    return max(Decimal("0"), min(Decimal("100"), value))


def _score_to_recommendation(score: Decimal) -> Recommendation:
    """Map 0-10 score to recommendation."""
    if score <= Decimal("2"):
        return Recommendation.STRONG_SELL
    if score <= Decimal("4"):
        return Recommendation.SELL
    if score <= Decimal("6"):
        return Recommendation.HOLD
    if score <= Decimal("8"):
        return Recommendation.BUY
    return Recommendation.STRONG_BUY


class FinancialScoringEngine:
    """Weighted scoring model for financial health."""

    def calculate(
        self,
        symbol: str,
        period: str,
        ratios: list[FinancialRatio],
        valuation: Valuation | None = None,
        *,
        profile: FinancialProfile = FinancialProfile.GENERAL,
        investment_ready: bool = True,
    ) -> FinancialScore:
        """Calculate composite financial score from ratios."""
        latest = ratios[-1] if ratios else None

        if profile == FinancialProfile.BANK:
            growth = self._score_bank_growth(latest)
            profitability = self._score_bank_profitability(latest)
            debt = Decimal("50")
            cash_flow = Decimal("50")
            val_score = self._score_bank_valuation(latest, valuation)
        else:
            growth = self._score_growth(latest, ratios)
            profitability = self._score_profitability(latest)
            debt = self._score_debt(latest)
            cash_flow = self._score_cash_flow(latest)
            val_score = self._score_valuation(latest, valuation)

        categories = (
            CategoryScore("Growth", growth, WEIGHTS["growth"], growth * WEIGHTS["growth"]),
            CategoryScore(
                "Profitability",
                profitability,
                WEIGHTS["profitability"],
                profitability * WEIGHTS["profitability"],
            ),
            CategoryScore("Debt", debt, WEIGHTS["debt"], debt * WEIGHTS["debt"]),
            CategoryScore(
                "Cash Flow",
                cash_flow,
                WEIGHTS["cash_flow"],
                cash_flow * WEIGHTS["cash_flow"],
            ),
            CategoryScore(
                "Valuation",
                val_score,
                WEIGHTS["valuation"],
                val_score * WEIGHTS["valuation"],
            ),
        )

        overall_pct = sum(c.weighted_score for c in categories)
        overall = (overall_pct / Decimal("10")).quantize(Decimal("0.1"))

        return FinancialScore(
            symbol=symbol,
            period=period,
            overall_score=overall,
            recommendation=(
                _score_to_recommendation(overall) if investment_ready else Recommendation.HOLD
            ),
            growth_score=(growth / Decimal("10")).quantize(Decimal("0.1")),
            profitability_score=(profitability / Decimal("10")).quantize(Decimal("0.1")),
            debt_score=(debt / Decimal("10")).quantize(Decimal("0.1")),
            cash_flow_score=(cash_flow / Decimal("10")).quantize(Decimal("0.1")),
            valuation_score=(val_score / Decimal("10")).quantize(Decimal("0.1")),
            categories=categories,
        )

    def _score_bank_growth(self, latest: FinancialRatio | None) -> Decimal:
        if latest is None or latest.profit_growth is None:
            return Decimal("50")
        if latest.profit_growth > Decimal("20"):
            return Decimal("80")
        if latest.profit_growth > Decimal("10"):
            return Decimal("65")
        if latest.profit_growth > Decimal("0"):
            return Decimal("55")
        return Decimal("35")

    def _score_bank_profitability(self, latest: FinancialRatio | None) -> Decimal:
        if latest is None:
            return Decimal("50")
        score = Decimal("50")
        if latest.roe is not None:
            score += Decimal("25") if latest.roe > Decimal("18") else Decimal("10")
        if latest.roa is not None:
            score += Decimal("15") if latest.roa > Decimal("1.5") else Decimal("5")
        return _clamp_score(score)

    def _score_bank_valuation(
        self,
        latest: FinancialRatio | None,
        valuation: Valuation | None,
    ) -> Decimal:
        score = Decimal("50")
        if valuation is not None and valuation.status.value == "UNDERVALUED":
            score += Decimal("20")
        elif valuation is not None and valuation.status.value == "OVERVALUED":
            score -= Decimal("20")
        if latest is not None and latest.pb is not None:
            if latest.pb < Decimal("1"):
                score += Decimal("15")
            elif latest.pb > Decimal("2.5"):
                score -= Decimal("15")
        return _clamp_score(score)

    def _score_growth(
        self,
        latest: FinancialRatio | None,
        all_ratios: list[FinancialRatio],
    ) -> Decimal:
        if latest is None:
            return Decimal("50")
        score = Decimal("50")
        if latest.revenue_growth is not None:
            if latest.revenue_growth > Decimal("15"):
                score += Decimal("25")
            elif latest.revenue_growth > Decimal("5"):
                score += Decimal("15")
            elif latest.revenue_growth > Decimal("0"):
                score += Decimal("5")
            else:
                score -= Decimal("15")
        if latest.profit_growth is not None:
            if latest.profit_growth > Decimal("20"):
                score += Decimal("15")
            elif latest.profit_growth > Decimal("0"):
                score += Decimal("5")
            else:
                score -= Decimal("10")
        if latest.eps_growth is not None and latest.eps_growth > Decimal("10"):
            score += Decimal("10")
        return _clamp_score(score)

    def _score_profitability(self, latest: FinancialRatio | None) -> Decimal:
        if latest is None:
            return Decimal("50")
        score = Decimal("50")
        if latest.roe is not None:
            if latest.roe > Decimal("20"):
                score += Decimal("20")
            elif latest.roe > Decimal("15"):
                score += Decimal("10")
            elif latest.roe < Decimal("10"):
                score -= Decimal("15")
        if latest.net_margin is not None:
            if latest.net_margin > Decimal("15"):
                score += Decimal("15")
            elif latest.net_margin > Decimal("5"):
                score += Decimal("5")
            else:
                score -= Decimal("10")
        if latest.gross_margin is not None and latest.gross_margin > Decimal("30"):
            score += Decimal("10")
        return _clamp_score(score)

    def _score_debt(self, latest: FinancialRatio | None) -> Decimal:
        if latest is None:
            return Decimal("50")
        score = Decimal("50")
        if latest.debt_to_equity is not None:
            if latest.debt_to_equity < Decimal("0.5"):
                score += Decimal("25")
            elif latest.debt_to_equity < Decimal("1.0"):
                score += Decimal("10")
            elif latest.debt_to_equity > Decimal("2.0"):
                score -= Decimal("20")
        if latest.current_ratio is not None:
            if latest.current_ratio > Decimal("1.5"):
                score += Decimal("15")
            elif latest.current_ratio < Decimal("1.0"):
                score -= Decimal("15")
        if latest.quick_ratio is not None and latest.quick_ratio > Decimal("1.0"):
            score += Decimal("10")
        return _clamp_score(score)

    def _score_cash_flow(self, latest: FinancialRatio | None) -> Decimal:
        if latest is None:
            return Decimal("50")
        score = Decimal("50")
        if latest.operating_cash_flow is not None and latest.operating_cash_flow > 0:
            score += Decimal("20")
        elif latest.operating_cash_flow is not None and latest.operating_cash_flow < 0:
            score -= Decimal("20")
        if latest.free_cash_flow is not None and latest.free_cash_flow > 0:
            score += Decimal("15")
        if latest.fcf_growth is not None and latest.fcf_growth > Decimal("0"):
            score += Decimal("10")
        if latest.cash_conversion is not None and latest.cash_conversion > Decimal("0.8"):
            score += Decimal("10")
        return _clamp_score(score)

    def _score_valuation(
        self,
        latest: FinancialRatio | None,
        valuation: Valuation | None,
    ) -> Decimal:
        score = Decimal("50")
        if valuation is not None:
            if valuation.status.value == "UNDERVALUED":
                score += Decimal("25")
            elif valuation.status.value == "FAIR":
                score += Decimal("5")
            else:
                score -= Decimal("15")
        if latest is not None and latest.pe is not None:
            if latest.pe < Decimal("15"):
                score += Decimal("15")
            elif latest.pe > Decimal("30"):
                score -= Decimal("15")
        if latest is not None and latest.pb is not None:
            if latest.pb < Decimal("2"):
                score += Decimal("10")
            elif latest.pb > Decimal("4"):
                score -= Decimal("10")
        return _clamp_score(score)
