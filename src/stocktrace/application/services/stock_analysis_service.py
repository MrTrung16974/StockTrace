"""Application service for AI-backed stock analysis."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from stocktrace.ai.analysis_service import AnalysisService
from stocktrace.ai.models import AnalysisContext, AnalysisMode, HistoricalPoint, StockAnalysisResult
from stocktrace.ai.translation_service import TranslationService
from stocktrace.application.queries.stock_handlers import (
    GetStockNewsQueryHandler,
    GetStockQuoteQueryHandler,
)
from stocktrace.application.queries.stock_queries import GetNewsQuery, GetPriceQuery
from stocktrace.application.services.fundamental_analysis_service import FundamentalAnalysisService
from stocktrace.application.services.liquidity_analysis_service import (
    LiquidityAnalysisService,
    LiquidityAssessment,
)
from stocktrace.application.services.market_data import (
    FundamentalData,
    HistoricalPrice,
    MarketDataService,
    NewsArticle,
    StockQuote,
)
from stocktrace.application.services.news_analysis_service import NewsAnalysisService, NewsSentimentResult
from stocktrace.application.services.news_quality import select_recent_unique_news
from stocktrace.application.services.stock_score_service import StockScore, StockScoreService
from stocktrace.application.services.technical_analysis_service import (
    TechnicalAnalysisService,
    TechnicalIndicators,
)
from stocktrace.domain.ports.ai_cache import AICache
from stocktrace.domain.ports.historical_provider import HistoricalProvider
from stocktrace.infrastructure.config.settings import AISettings
from stocktrace.infrastructure.logging.config import get_logger

_DEFAULT_NEWS_LIMIT = 5
_HISTORICAL_DAYS = 250


@dataclass(frozen=True, slots=True)
class AnalysisBundle:
    """Gathered market data and AI analysis for a symbol."""

    symbol: str
    quote: StockQuote | None
    news: tuple[NewsArticle, ...]
    analysis: StockAnalysisResult | None
    historical: tuple[HistoricalPoint, ...] = ()
    technical: TechnicalIndicators | None = None
    fundamentals: dict[str, str] | None = None
    fundamental_raw: FundamentalData | None = None
    liquidity: LiquidityAssessment | None = None
    news_sentiment: NewsSentimentResult | None = None
    score: StockScore | None = None
    price_history: tuple[HistoricalPrice, ...] = ()


class StockAnalysisService:
    """Gather market data, run quantitative analysis, and delegate to AI."""

    def __init__(
        self,
        quote_handler: GetStockQuoteQueryHandler,
        news_handler: GetStockNewsQueryHandler,
        analysis_service: AnalysisService,
        market_data_service: MarketDataService,
        translation_service: TranslationService | None = None,
        historical_provider: HistoricalProvider | None = None,
        technical_service: TechnicalAnalysisService | None = None,
        fundamental_service: FundamentalAnalysisService | None = None,
        news_analysis_service: NewsAnalysisService | None = None,
        liquidity_service: LiquidityAnalysisService | None = None,
        score_service: StockScoreService | None = None,
        report_cache: AICache | None = None,
        ai_settings: AISettings | None = None,
    ) -> None:
        self._quote_handler = quote_handler
        self._news_handler = news_handler
        self._analysis_service = analysis_service
        self._market_data_service = market_data_service
        self._translation_service = translation_service
        self._historical_provider = historical_provider
        self._technical_service = technical_service or TechnicalAnalysisService()
        self._fundamental_service = fundamental_service or FundamentalAnalysisService()
        self._news_analysis_service = news_analysis_service or NewsAnalysisService()
        self._liquidity_service = liquidity_service or LiquidityAnalysisService()
        self._score_service = score_service or StockScoreService()
        self._report_cache = report_cache
        self._ai_settings = ai_settings
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
        """Fetch market data, run quantitative + AI analysis."""
        normalized = symbol.strip().upper()
        cache_key = f"full_report:{normalized}:{mode.value}:{news_limit}"
        cached = await self._get_cached_report(cache_key)
        if cached is not None:
            self._logger.info("analysis_report_cache_hit", symbol=normalized)
            return cached

        quote = await self._safe_get_quote(normalized)
        articles = await self._news_handler.handle(
            GetNewsQuery(symbol=normalized, limit=news_limit),
        )
        articles = await self._maybe_translate(normalized, articles)
        historical = await self._safe_get_historical(normalized)
        news_sentiment = self._news_analysis_service.analyze(articles, limit=news_limit)

        technical: TechnicalIndicators | None = None
        fundamentals: dict[str, str] | None = None
        fundamental_raw: FundamentalData | None = None
        liquidity: LiquidityAssessment | None = None
        score: StockScore | None = None

        hist_prices = await self._safe_get_historical_prices(normalized)
        if hist_prices:
            technical = self._technical_service.analyze(hist_prices)

        fundamental_raw = await self._safe_get_fundamentals(normalized)
        if fundamental_raw is not None:
            fundamentals = self._fundamental_service.analyze(fundamental_raw)
            liquidity = self._liquidity_service.analyze(quote, hist_prices, fundamental_raw)

        if technical is not None and fundamentals is not None and liquidity is not None:
            score = self._score_service.calculate_score(
                technical,
                fundamentals,
                news_sentiment.label,
                liquidity.status,
            )

        analysis = None
        if self.is_enabled:
            context = AnalysisContext(
                symbol=normalized,
                news=tuple(articles),
                mode=mode,
                price=quote,
                historical=tuple(historical),
                technical_indicators=_technical_dict(technical),
                fundamental_data=fundamentals,
                score=_score_dict(score),
            )
            analysis = await self._analysis_service.analyze(context)

        bundle = AnalysisBundle(
            symbol=normalized,
            quote=quote,
            news=tuple(articles),
            analysis=analysis,
            historical=tuple(historical),
            technical=technical,
            fundamentals=fundamentals,
            fundamental_raw=fundamental_raw,
            liquidity=liquidity,
            news_sentiment=news_sentiment,
            score=score,
            price_history=tuple(hist_prices),
        )
        await self._set_cached_report(cache_key, bundle)
        return bundle

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
        articles = select_recent_unique_news(articles, limit=limit)
        articles = await self._maybe_translate(normalized, articles)
        analysis = await self.analyze_news(normalized, articles, include_price=True)
        return articles, analysis

    async def _get_cached_report(self, cache_key: str) -> AnalysisBundle | None:
        if self._report_cache is None:
            return None
        try:
            payload = await self._report_cache.get(cache_key)
        except Exception:
            return None
        if payload is None:
            return None
        try:
            return _bundle_from_cache(payload)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

    async def _set_cached_report(self, cache_key: str, bundle: AnalysisBundle) -> None:
        if self._report_cache is None or self._ai_settings is None:
            return
        try:
            await self._report_cache.set(
                cache_key,
                _bundle_to_cache(bundle),
                ttl_seconds=self._ai_settings.report_cache_ttl_seconds,
            )
        except Exception as exc:
            self._logger.warning("analysis_report_cache_set_failed", error=str(exc))

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

    async def _safe_get_historical_prices(self, symbol: str):
        try:
            return await self._market_data_service.get_historical_prices(
                symbol,
                days=_HISTORICAL_DAYS,
            )
        except Exception as exc:
            self._logger.warning("historical_prices_fetch_failed", symbol=symbol, error=str(exc))
            return []

    async def _safe_get_fundamentals(self, symbol: str) -> FundamentalData | None:
        try:
            return await self._market_data_service.get_fundamental_data(symbol)
        except Exception as exc:
            self._logger.warning("fundamental_fetch_failed", symbol=symbol, error=str(exc))
            return None


def _technical_dict(technical: TechnicalIndicators | None) -> dict | None:
    if technical is None:
        return None
    return {key: str(value) if value is not None else None for key, value in asdict(technical).items()}


def _score_dict(score: StockScore | None) -> dict | None:
    if score is None:
        return None
    return asdict(score)


def _bundle_to_cache(bundle: AnalysisBundle) -> str:
    payload = {
        "symbol": bundle.symbol,
        "quote": _quote_to_dict(bundle.quote),
        "news": [_news_to_dict(item) for item in bundle.news],
        "analysis": _analysis_to_dict(bundle.analysis),
        "technical": asdict(bundle.technical) if bundle.technical else None,
        "fundamentals": bundle.fundamentals,
        "fundamental_raw": asdict(bundle.fundamental_raw) if bundle.fundamental_raw else None,
        "liquidity": asdict(bundle.liquidity) if bundle.liquidity else None,
        "news_sentiment": asdict(bundle.news_sentiment) if bundle.news_sentiment else None,
        "score": asdict(bundle.score) if bundle.score else None,
        "price_history": [_historical_price_to_dict(item) for item in bundle.price_history],
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


def _bundle_from_cache(payload: str) -> AnalysisBundle:
    data = json.loads(payload)
    return AnalysisBundle(
        symbol=data["symbol"],
        quote=_quote_from_dict(data.get("quote")),
        news=tuple(_news_from_dict(item) for item in data.get("news", [])),
        analysis=_analysis_from_dict(data.get("analysis")),
        technical=_technical_from_dict(data.get("technical")),
        fundamentals=data.get("fundamentals"),
        fundamental_raw=_fundamental_from_dict(data.get("fundamental_raw")),
        liquidity=_liquidity_from_dict(data.get("liquidity")),
        news_sentiment=_news_sentiment_from_dict(data.get("news_sentiment")),
        score=_score_from_dict(data.get("score")),
        price_history=tuple(_historical_price_from_dict(item) for item in data.get("price_history", [])),
    )


def _quote_to_dict(quote: StockQuote | None) -> dict | None:
    if quote is None:
        return None
    return {key: str(value) for key, value in asdict(quote).items()}


def _quote_from_dict(data: dict | None) -> StockQuote | None:
    if not data:
        return None
    from datetime import datetime
    from decimal import Decimal

    return StockQuote(
        ticker=data["ticker"],
        company_name=data["company_name"],
        current_price=Decimal(data["current_price"]),
        change=Decimal(data["change"]),
        change_percent=Decimal(data["change_percent"]),
        open_price=Decimal(data["open_price"]),
        high_price=Decimal(data["high_price"]),
        low_price=Decimal(data["low_price"]),
        volume=int(data["volume"]),
        timestamp=datetime.fromisoformat(data["timestamp"]),
        currency=data.get("currency", "VND"),
        source=data.get("source", "Unknown"),
    )


def _news_to_dict(article: NewsArticle) -> dict:
    return {
        "ticker": article.ticker,
        "title": article.title,
        "summary": article.summary,
        "url": article.url,
        "source": article.source,
        "published_at": article.published_at.isoformat() if article.published_at else None,
    }


def _news_from_dict(data: dict) -> NewsArticle:
    from datetime import datetime

    published = data.get("published_at")
    return NewsArticle(
        ticker=data["ticker"],
        title=data["title"],
        summary=data.get("summary"),
        url=data["url"],
        source=data["source"],
        published_at=datetime.fromisoformat(published) if published else None,
    )


def _analysis_to_dict(analysis: StockAnalysisResult | None) -> dict | None:
    if analysis is None:
        return None
    data = asdict(analysis)
    data["sentiment"] = analysis.sentiment.value
    return data


def _analysis_from_dict(data: dict | None) -> StockAnalysisResult | None:
    if not data:
        return None
    from stocktrace.ai.models import SentimentLabel

    data = dict(data)
    data["sentiment"] = SentimentLabel(str(data.get("sentiment", SentimentLabel.NEUTRAL.value)))
    return StockAnalysisResult(**data)


def _technical_from_dict(data: dict | None) -> TechnicalIndicators | None:
    if not data:
        return None
    from decimal import Decimal

    converted = {}
    for key, value in data.items():
        if key.endswith("_trend") or key == "signal":
            converted[key] = value
        elif value is None:
            converted[key] = None
        else:
            converted[key] = Decimal(str(value))
    return TechnicalIndicators(**converted)


def _fundamental_from_dict(data: dict | None) -> FundamentalData | None:
    if not data:
        return None
    from decimal import Decimal

    return FundamentalData(
        eps=Decimal(data["eps"]) if data.get("eps") is not None else None,
        pe=Decimal(data["pe"]) if data.get("pe") is not None else None,
        pb=Decimal(data["pb"]) if data.get("pb") is not None else None,
        roe=Decimal(data["roe"]) if data.get("roe") is not None else None,
        roa=Decimal(data["roa"]) if data.get("roa") is not None else None,
        foreign_buy_vol=data.get("foreign_buy_vol"),
        foreign_sell_vol=data.get("foreign_sell_vol"),
    )


def _liquidity_from_dict(data: dict | None) -> LiquidityAssessment | None:
    if not data:
        return None
    from decimal import Decimal

    return LiquidityAssessment(
        avg_volume_20d=int(data["avg_volume_20d"]),
        current_volume=int(data["current_volume"]),
        volume_ratio=Decimal(str(data["volume_ratio"])),
        foreign_buy_vol=data.get("foreign_buy_vol"),
        foreign_sell_vol=data.get("foreign_sell_vol"),
        foreign_net_vol=data.get("foreign_net_vol"),
        status=data["status"],
        foreign_flow_label=data["foreign_flow_label"],
    )


def _news_sentiment_from_dict(data: dict | None) -> NewsSentimentResult | None:
    if not data:
        return None
    return NewsSentimentResult(**data)


def _score_from_dict(data: dict | None) -> StockScore | None:
    if not data:
        return None
    return StockScore(**data)


def _historical_price_to_dict(point: HistoricalPrice) -> dict:
    return {
        "date": point.date.isoformat(),
        "open": str(point.open),
        "high": str(point.high),
        "low": str(point.low),
        "close": str(point.close),
        "volume": point.volume,
    }


def _historical_price_from_dict(data: dict) -> HistoricalPrice:
    from datetime import datetime
    from decimal import Decimal

    return HistoricalPrice(
        date=datetime.fromisoformat(data["date"]),
        open=Decimal(data["open"]),
        high=Decimal(data["high"]),
        low=Decimal(data["low"]),
        close=Decimal(data["close"]),
        volume=int(data["volume"]),
    )
