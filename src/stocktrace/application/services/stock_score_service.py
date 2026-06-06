"""Stock Scoring Service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stocktrace.application.services.technical_analysis_service import TechnicalIndicators

@dataclass
class StockScore:
    """Calculated stock scores."""
    technical_score: int
    fundamental_score: int
    news_score: int
    momentum_score: int
    overall_score: int
    stars: str

class StockScoreService:
    """Service to calculate stock scores."""

    def calculate_score(
        self,
        tech: TechnicalIndicators,
        fundamentals: dict[str, str],
        news_sentiment: str,
        liquidity_status: str
    ) -> StockScore:
        """Calculate overall and individual scores."""
        # Technical Score
        tech_score = 50
        if tech.short_term_trend == "Tăng":
            tech_score += 15
        elif tech.short_term_trend == "Giảm":
            tech_score -= 15
        
        if tech.mid_term_trend == "Tăng":
            tech_score += 10
        elif tech.mid_term_trend == "Giảm":
            tech_score -= 10
            
        if tech.rsi:
            if 30 <= tech.rsi <= 70:
                tech_score += 5
            elif tech.rsi < 30:
                tech_score += 10 # Oversold
            else:
                tech_score -= 10 # Overbought
                
        if tech.macd_hist and tech.macd_hist > 0:
            tech_score += 10
        else:
            tech_score -= 10
            
        tech_score = max(0, min(100, tech_score))

        # Fundamental Score
        fund_score = 50
        fund_map = {"Rất tốt": 10, "Tốt": 5, "Trung bình": 0, "Yếu": -10, "Chưa rõ": 0}
        for k, v in fundamentals.items():
            fund_score += fund_map.get(v, 0)
        fund_score = max(0, min(100, fund_score))

        # News Score
        news_score = 50
        if "Tích cực" in news_sentiment:
            news_score += 30
        elif "Tiêu cực" in news_sentiment:
            news_score -= 30
        news_score = max(0, min(100, news_score))

        # Momentum / Liquidity Score
        mom_score = 50
        if liquidity_status == "Thanh khoản cao":
            mom_score += 30
        elif liquidity_status == "Thanh khoản yếu":
            mom_score -= 20
        mom_score = max(0, min(100, mom_score))

        # Overall
        overall = int((tech_score * 0.4) + (fund_score * 0.3) + (news_score * 0.15) + (mom_score * 0.15))
        
        # Stars
        if overall >= 90:
            stars = "⭐⭐⭐⭐⭐"
        elif overall >= 80:
            stars = "⭐⭐⭐⭐"
        elif overall >= 70:
            stars = "⭐⭐⭐"
        elif overall >= 60:
            stars = "⭐⭐"
        else:
            stars = "⭐"

        return StockScore(
            technical_score=tech_score,
            fundamental_score=fund_score,
            news_score=news_score,
            momentum_score=mom_score,
            overall_score=overall,
            stars=stars
        )
