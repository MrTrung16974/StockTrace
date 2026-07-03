"""Application service for market-wide AI analysis."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, UTC

from stocktrace.ai.analysis_service import AnalysisService
from stocktrace.ai.models import MarketAnalysisContext, MarketAnalysisResult
from stocktrace.application.services.market_data import MarketDataService, NewsArticle, StockQuote
from stocktrace.infrastructure.logging.config import get_logger

INDICES = {"VNINDEX": "^VNINDEX", "VN30": "^VN30", "HNX": "^HNXINDEX", "UPCOM": None}
SECTORS = {
    "Ngân hàng": "VCB",
    "Chứng khoán": "SSI",
    "Bất động sản": "VHM",
    "Thép": "HPG",
    "Công nghệ": "FPT",
    "Bán lẻ": "MWG",
    "Năng lượng": "POW",
}
INTERNATIONAL = {
    "S&P500": "^GSPC",
    "Nasdaq": "^IXIC",
    "Dow Jones": "^DJI",
    "DXY": "DX-Y.NYB",
    "Dầu thô": "CL=F",
    "Vàng": "GC=F",
    "Bitcoin": "BTC-USD",
}
MARKET_NEWS_QUERY = "thị trường chứng khoán Việt Nam kinh tế"


@dataclass(frozen=True, slots=True)
class MarketAnalysisBundle:
    """Gathered market data and AI analysis for the whole market."""

    timestamp: datetime
    indices: dict[str, StockQuote | None]
    sectors: dict[str, StockQuote | None]
    international: dict[str, StockQuote | None]
    news: tuple[NewsArticle, ...]
    analysis: MarketAnalysisResult | None


class MarketAnalysisService:
    """Gather market-wide data and delegate to AI for macro analysis."""

    def __init__(
        self,
        analysis_service: AnalysisService,
        market_data_service: MarketDataService,
    ) -> None:
        self._analysis_service = analysis_service
        self._market_data_service = market_data_service
        self._logger = get_logger(__name__)

    @property
    def is_enabled(self) -> bool:
        """Return whether AI analysis is available."""
        return self._analysis_service.is_configured

    async def analyze_market(self, news_limit: int = 10) -> MarketAnalysisBundle:
        """Fetch market data and run AI analysis."""
        self._logger.info("market_analysis_started")
        
        # 1. Fetch all data concurrently
        indices_task = self._fetch_dict(INDICES)
        sectors_task = self._fetch_dict(SECTORS)
        international_task = self._fetch_dict(INTERNATIONAL)
        news_task = self._fetch_news(MARKET_NEWS_QUERY, limit=news_limit)

        indices, sectors, international, news = await asyncio.gather(
            indices_task, sectors_task, international_task, news_task, return_exceptions=True
        )

        # Handle potential exceptions from gather
        indices = indices if isinstance(indices, dict) else {k: None for k in INDICES}
        sectors = sectors if isinstance(sectors, dict) else {k: None for k in SECTORS}
        international = international if isinstance(international, dict) else {k: None for k in INTERNATIONAL}
        news = news if isinstance(news, list) else []

        # 2. AI Analysis
        analysis: MarketAnalysisResult | None = None
        if self.is_enabled:
            context = MarketAnalysisContext(
                indices=indices,
                sectors=sectors,
                international=international,
                news=tuple(news),
            )
            analysis = await self._analysis_service.analyze_market(context)

        bundle = MarketAnalysisBundle(
            timestamp=datetime.now(UTC),
            indices=indices,
            sectors=sectors,
            international=international,
            news=tuple(news),
            analysis=analysis,
        )
        self._logger.info("market_analysis_completed", has_analysis=analysis is not None)
        return bundle

    async def _fetch_dict(self, mapping: dict[str, str | None]) -> dict[str, StockQuote | None]:
        results: dict[str, StockQuote | None] = {}
        # Fetch sequentially to avoid rate limits, or we could chunk them
        for name, ticker in mapping.items():
            if ticker is None:
                results[name] = None
                continue
            try:
                # Need to use the raw provider directly or quote handler to skip symbol validation if it's strict
                # Wait, MarketDataService uses get_quote which normalizes symbols
                quote = await self._market_data_service.get_quote(ticker)
                results[name] = quote
            except Exception as exc:
                self._logger.warning("market_analysis_fetch_quote_failed", ticker=ticker, error=str(exc))
                results[name] = None
            await asyncio.sleep(0.1) # small delay
        return results

    async def _fetch_news(self, query: str, limit: int) -> list[NewsArticle]:
        try:
            return await self._market_data_service.get_news(query, limit=limit)
        except Exception as exc:
            self._logger.warning("market_analysis_fetch_news_failed", query=query, error=str(exc))
            return []
