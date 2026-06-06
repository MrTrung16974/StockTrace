"""Fundamental Analysis Service."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stocktrace.application.services.market_data import FundamentalData

class FundamentalAnalysisService:
    """Service to perform fundamental analysis."""

    def analyze(self, data: FundamentalData) -> dict[str, str]:
        """Analyze fundamental metrics and return their evaluation."""
        evaluations = {}
        
        # PE Evaluation
        if data.pe is not None:
            if data.pe < 10:
                evaluations["PE"] = "Rất tốt"
            elif 10 <= data.pe <= 15:
                evaluations["PE"] = "Tốt"
            elif 15 < data.pe <= 25:
                evaluations["PE"] = "Trung bình"
            else:
                evaluations["PE"] = "Yếu"
        else:
            evaluations["PE"] = "Chưa rõ"

        # PB Evaluation
        if data.pb is not None:
            if data.pb < 1:
                evaluations["PB"] = "Rất tốt"
            elif 1 <= data.pb <= 2:
                evaluations["PB"] = "Tốt"
            elif 2 < data.pb <= 4:
                evaluations["PB"] = "Trung bình"
            else:
                evaluations["PB"] = "Yếu"
        else:
            evaluations["PB"] = "Chưa rõ"

        # ROE Evaluation
        if data.roe is not None:
            if data.roe > 20:
                evaluations["ROE"] = "Rất tốt"
            elif 15 <= data.roe <= 20:
                evaluations["ROE"] = "Tốt"
            elif 10 <= data.roe < 15:
                evaluations["ROE"] = "Trung bình"
            else:
                evaluations["ROE"] = "Yếu"
        else:
            evaluations["ROE"] = "Chưa rõ"

        # EPS Evaluation (just a simple positive/negative check)
        if data.eps is not None:
            if data.eps > 2000:
                evaluations["EPS"] = "Rất tốt"
            elif 1000 <= data.eps <= 2000:
                evaluations["EPS"] = "Tốt"
            elif 0 < data.eps < 1000:
                evaluations["EPS"] = "Trung bình"
            else:
                evaluations["EPS"] = "Yếu"
        else:
            evaluations["EPS"] = "Chưa rõ"

        return evaluations
