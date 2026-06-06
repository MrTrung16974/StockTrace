"""Application service for AI-backed stock analysis."""

from __future__ import annotations

from dataclasses import dataclass

from stocktrace.ai.analysis_service import AnalysisService
from stocktrace.ai.models import AnalysisContext, AnalysisMode, HistoricalPoint, StockAnalysisResult
from stocktrace.ai.translation_service import TranslationService
from stocktrace.application.queries.stock_handlers import (
    GetStockNewsQueryHandler,
    GetStockQuoteQueryHandler,
)
from stocktrace.application.queries.stock_queries import GetNewsQuery, GetPriceQuery
from stocktrace.application.services.market_data import NewsArticle, StockQuote
from stocktrace.domain.ports.historical_provider import HistoricalProvider
from stocktrace.infrastructure.logging.config import get_logger

_DEFAULT_NEWS_LIMIT = 5


@dataclass(frozen=True, slots=True)
class AnalysisBundle:
    """Gathered market data and AI analysis for a symbol."""

    symbol: str
    quote: StockQuote | None
    news: tuple[NewsArticle, ...]
    analysis: StockAnalysisResult | None
    historical: tuple[HistoricalPoint, ...] = ()


class StockAnalysisService:
    """Gather market data and delegate to the AI analysis layer."""

    def __init__(
        self,
        quote_handler: GetStockQuoteQueryHandler,
        news_handler: GetStockNewsQueryHandler,
        analysis_service: AnalysisService,
        translation_service: TranslationService | None = None,
        historical_provider: HistoricalProvider | None = None,
        market_data_service=None,
    ) -> None:
        self._quote_handler = quote_handler
        self._news_handler = news_handler
        self._analysis_service = analysis_service
        self._translation_service = translation_service
        self._historical_provider = historical_provider
        self._market_data_service = market_data_service
        self._logger = get_logger(__name__)

    @property
    def is_enabled(self) -> bool:
        """Return whether AI analysis is available."""
        return self._analysis_service.is_configured

    async def analyze_symbol(
        self,
        symbol: str,
        *,
        mode: AnalysisMode = AnalysisMode.FULL,
        news_limit: int = _DEFAULT_NEWS_LIMIT,
    ) -> AnalysisBundle:
        """Fetch market data and run AI analysis."""
        normalized = symbol.strip().upper()
        quote = await self._safe_get_quote(normalized)
        articles = await self._news_handler.handle(
            GetNewsQuery(symbol=normalized, limit=news_limit),
        )
        articles = await self._maybe_translate(normalized, articles)
        historical = await self._safe_get_historical(normalized)
        
        technical_indicators = None
        fundamental_data = None
        score = None
        
        if self._market_data_service is not None:
            try:
                hist_prices = await self._market_data_service.get_historical_prices(normalized, days=200)
                if hist_prices:
                    from stocktrace.application.services.technical_analysis_service import TechnicalAnalysisService
                    tech_service = TechnicalAnalysisService()
                    technical_indicators = tech_service.analyze(hist_prices).__dict__
            except Exception as e:
                self._logger.warning("ai_technical_analysis_failed", symbol=normalized, error=str(e))
                
            try:
                fund_data = await self._market_data_service.get_fundamental_data(normalized)
                if fund_data:
                    from stocktrace.application.services.fundamental_analysis_service import FundamentalAnalysisService
                    fund_service = FundamentalAnalysisService()
                    fundamental_data = fund_service.analyze(fund_data)
            except Exception as e:
                self._logger.warning("ai_fundamental_analysis_failed", symbol=normalized, error=str(e))
                
            try:
                if technical_indicators and fundamental_data is not None:
                    from stocktrace.application.services.stock_score_service import StockScoreService
                    from stocktrace.application.services.technical_analysis_service import TechnicalIndicators
                    score_service = StockScoreService()
                    # Determine liquidity status from technical indicators
                    liquidity = "Thanh khoản trung bình"
                    # Determine news sentiment
                    news_text = " ".join(a.title for a in articles).lower()
                    sentiment = "Trung lập"
                    if any(w in news_text for w in ["tăng", "lãi", "tích cực"]): sentiment = "Tích cực"
                    elif any(w in news_text for w in ["giảm", "lỗ", "tiêu cực"]): sentiment = "Tiêu cực"
                    
                    tech_ind = TechnicalIndicators(**technical_indicators)
                    stock_score = score_service.calculate_score(tech_ind, fundamental_data, sentiment, liquidity)
                    score = stock_score.__dict__
            except Exception as e:
                self._logger.warning("ai_score_calculation_failed", symbol=normalized, error=str(e))

        analysis = None
        if self.is_enabled:
            context = AnalysisContext(
                symbol=normalized,
                news=tuple(articles),
                mode=mode,
                price=quote,
                historical=tuple(historical),
                technical_indicators=technical_indicators,
                fundamental_data=fundamental_data,
                score=score,
            )
            analysis = await self._analysis_service.analyze(context)

        return AnalysisBundle(
            symbol=normalized,
            quote=quote,
            news=tuple(articles),
            analysis=analysis,
            historical=tuple(historical),
        )

    async def analyze_news(
        self,
        symbol: str,
        articles: list[NewsArticle],
        *,
        include_price: bool = True,
    ) -> StockAnalysisResult | None:
        """Analyze news context for /news command append."""
        if not self.is_enabled:
            return None

        normalized = symbol.strip().upper()
        quote = await self._safe_get_quote(normalized) if include_price else None
        translated = await self._maybe_translate(normalized, articles)

        context = AnalysisContext(
            symbol=normalized,
            news=tuple(translated),
            mode=AnalysisMode.NEWS_ONLY,
            price=quote,
        )
        return await self._analysis_service.analyze(context)

    async def fetch_and_analyze_news(
        self,
        symbol: str,
        *,
        limit: int = _DEFAULT_NEWS_LIMIT,
    ) -> tuple[list[NewsArticle], StockAnalysisResult | None]:
        """Fetch news, optionally translate, and run AI analysis."""
        normalized = symbol.strip().upper()
        articles = await self._news_handler.handle(GetNewsQuery(symbol=normalized, limit=limit))
        articles = await self._maybe_translate(normalized, articles)
        analysis = await self.analyze_news(normalized, articles, include_price=True)
        return articles, analysis

    async def _maybe_translate(self, symbol: str, articles: list[NewsArticle]) -> list[NewsArticle]:
        if self._translation_service is None or not self._translation_service.is_configured:
            return articles
        try:
            return await self._translation_service.translate_articles(symbol, articles)
        except Exception as exc:
            self._logger.warning("ai_translation_skipped", symbol=symbol, error=str(exc))
            return articles

    async def _safe_get_quote(self, symbol: str) -> StockQuote | None:
        try:
            return await self._quote_handler.handle(GetPriceQuery(symbol=symbol))
        except Exception as exc:
            self._logger.warning("ai_quote_fetch_failed", symbol=symbol, error=str(exc))
            return None

    async def _safe_get_historical(self, symbol: str) -> list[HistoricalPoint]:
        if self._historical_provider is None:
            return []
        try:
            return await self._historical_provider.get_recent(symbol)
        except Exception as exc:
            self._logger.warning("ai_historical_fetch_failed", symbol=symbol, error=str(exc))
            return []
