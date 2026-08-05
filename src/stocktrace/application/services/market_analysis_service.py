"""Application service for market-wide AI analysis."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from stocktrace.ai.analysis_service import AnalysisService
from stocktrace.ai.models import MarketAnalysisContext, MarketAnalysisResult
from stocktrace.application.services.market_data import (
    MarketDataService,
    NewsArticle,
    StockQuote,
    VietnamIndexProvider,
)
from stocktrace.application.services.news_quality import select_recent_unique_news
from stocktrace.infrastructure.logging.config import get_logger

DOMESTIC_INDICES = ("VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX")
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
        vietnam_index_provider: VietnamIndexProvider | None = None,
    ) -> None:
        self._analysis_service = analysis_service
        self._market_data_service = market_data_service
        self._vietnam_index_provider = vietnam_index_provider
        self._logger = get_logger(__name__)

    @property
    def is_enabled(self) -> bool:
        """Return whether AI analysis is available."""
        return self._analysis_service.is_configured

    async def analyze_market(self, news_limit: int = 10) -> MarketAnalysisBundle:
        """Fetch market data and run AI analysis."""
        self._logger.info("market_analysis_started")

        # 1. Fetch indices and sectors first
        indices_task = self._fetch_domestic_indices()
        sectors_task = self._fetch_dict(SECTORS)
        international_task = self._fetch_dict(INTERNATIONAL)

        indices, sectors, international = await asyncio.gather(
            indices_task, sectors_task, international_task, return_exceptions=True
        )

        # Preserve a stable report shape when one of the external requests fails.
        indices = indices if isinstance(indices, dict) else dict.fromkeys(DOMESTIC_INDICES)
        sectors = sectors if isinstance(sectors, dict) else dict.fromkeys(SECTORS)
        international = (
            international
            if isinstance(international, dict)
            else dict.fromkeys(INTERNATIONAL)
        )

        # 2. Ưu tiên gọi phân tích AI trước mà không bị chặn bởi việc lấy tin từ Google News
        analysis_task = None
        if self.is_enabled:
            initial_context = MarketAnalysisContext(
                indices=indices,
                sectors=sectors,
                international=international,
                news=(),
            )
            analysis_task = asyncio.create_task(self._analysis_service.analyze_market(initial_context))

        # 3. Sau đó / đồng thời gọi Google News để lấy tin thị trường
        try:
            news_raw = await self._fetch_news(MARKET_NEWS_QUERY, limit=news_limit)
            news = select_recent_unique_news(news_raw if isinstance(news_raw, list) else [], limit=news_limit)
        except Exception as exc:
            self._logger.warning("market_news_fetch_failed_during_ai_priority", error=str(exc))
            news = []

        analysis: MarketAnalysisResult | None = await analysis_task if analysis_task else None

        # Nếu có tin thị trường từ Google News, cập nhật bổ sung vào bài phân tích AI
        if news and self.is_enabled:
            try:
                updated_context = MarketAnalysisContext(
                    indices=indices,
                    sectors=sectors,
                    international=international,
                    news=tuple(news),
                )
                updated_analysis = await self._analysis_service.analyze_market(updated_context)
                if updated_analysis is not None:
                    analysis = updated_analysis
            except Exception:
                pass

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

    async def _fetch_domestic_indices(self) -> dict[str, StockQuote | None]:
        """Use the Vietnam-focused provider instead of unsupported Yahoo symbols."""
        if self._vietnam_index_provider is None:
            return await self._fetch_dict(dict.fromkeys(DOMESTIC_INDICES))

        results: dict[str, StockQuote | None] = {}
        for symbol in DOMESTIC_INDICES:
            try:
                results[symbol] = await self._vietnam_index_provider.get_index_quote(symbol)
            except Exception as exc:
                self._logger.warning(
                    "market_analysis_fetch_vietnam_index_failed",
                    symbol=symbol,
                    error=str(exc),
                )
                results[symbol] = None
        return results

    async def _fetch_dict(self, mapping: dict[str, str | None]) -> dict[str, StockQuote | None]:
        results: dict[str, StockQuote | None] = {}
        # Fetch sequentially to avoid rate limits, or we could chunk them
        for name, ticker in mapping.items():
            if ticker is None:
                results[name] = None
                continue
            try:
                quote = await self._market_data_service.get_provider_quote(ticker)
                results[name] = quote
            except Exception as exc:
                self._logger.warning(
                    "market_analysis_fetch_quote_failed",
                    ticker=ticker,
                    error=str(exc),
                )
                results[name] = None
            await asyncio.sleep(0.1)
        return results

    async def _fetch_news(self, query: str, limit: int) -> list[NewsArticle]:
        try:
            return await self._market_data_service.get_market_news(query, limit=limit)
        except Exception as exc:
            self._logger.warning("market_analysis_fetch_news_failed", query=query, error=str(exc))
            return []
