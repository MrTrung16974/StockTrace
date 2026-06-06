"""Serialize and deserialize AI analysis results for caching."""

from __future__ import annotations

import json

from stocktrace.ai.models import SentimentLabel, StockAnalysisResult


def analysis_result_to_json(result: StockAnalysisResult) -> str:
    """Serialize a stock analysis result."""
    return json.dumps(
        {
            "symbol": result.symbol,
            "overview": result.overview,
            "positives": result.positives,
            "risks": result.risks,
            "short_term": result.short_term,
            "sentiment": result.sentiment.value,
            "medium_term": result.medium_term,
            "conclusion": result.conclusion,
            "positive_scenario": result.positive_scenario,
            "neutral_scenario": result.neutral_scenario,
            "negative_scenario": result.negative_scenario,
            "recommendation_action": result.recommendation_action,
            "recommendation_confidence": result.recommendation_confidence,
            "recommendation_reasons": result.recommendation_reasons,
            "raw_response": result.raw_response,
        },
        ensure_ascii=False,
    )


def analysis_result_from_json(payload: str) -> StockAnalysisResult:
    """Deserialize a stock analysis result."""
    data = json.loads(payload)
    return StockAnalysisResult(
        symbol=str(data["symbol"]),
        overview=str(data["overview"]),
        positives=str(data["positives"]),
        risks=str(data["risks"]),
        short_term=str(data["short_term"]),
        sentiment=SentimentLabel(str(data.get("sentiment", SentimentLabel.NEUTRAL.value))),
        medium_term=data.get("medium_term"),
        conclusion=data.get("conclusion"),
        positive_scenario=data.get("positive_scenario"),
        neutral_scenario=data.get("neutral_scenario"),
        negative_scenario=data.get("negative_scenario"),
        recommendation_action=data.get("recommendation_action"),
        recommendation_confidence=data.get("recommendation_confidence"),
        recommendation_reasons=data.get("recommendation_reasons"),
        raw_response=str(data.get("raw_response", "")),
    )
