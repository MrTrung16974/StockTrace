"""Core AI stock analysis orchestration."""

from __future__ import annotations

import hashlib
import json
import re
import time

from stocktrace.ai.models import (
    AnalysisContext,
    AnalysisMode,
    LLMResponse,
    MarketAnalysisContext,
    MarketAnalysisResult,
    SentimentLabel,
    StockAnalysisResult,
)
from stocktrace.ai.market_prompt_builder import MarketPromptBuilder
from stocktrace.ai.prompt_builder import PromptBuilder
from stocktrace.ai.serialization import analysis_result_from_json, analysis_result_to_json
from stocktrace.domain.ports.ai_cache import AICache
from stocktrace.domain.ports.llm_provider import LLMProvider
from stocktrace.infrastructure.config.settings import AISettings
from stocktrace.infrastructure.logging.config import get_logger

_SECTION_MARKERS = {
    "overview": ("[TỔNG QUAN]", "Tổng quan:"),
    "positives": ("[ĐIỂM TÍCH CỰC]", "Điểm tích cực:", "Điểm mạnh:"),
    "risks": ("[RỦI RO]", "Rủi ro:"),
    "short_term": ("[ĐÁNH GIÁ NGẮN HẠN]", "Đánh giá ngắn hạn:", "Ngắn hạn:"),
    "medium_term": ("[ĐÁNH GIÁ TRUNG HẠN]", "Đánh giá trung hạn:", "Trung hạn:"),
    "positive_scenario": ("[KỊCH BẢN TÍCH CỰC]", "Kịch bản tích cực:"),
    "neutral_scenario": ("[KỊCH BẢN TRUNG LẬP]", "Kịch bản trung lập:"),
    "negative_scenario": ("[KỊCH BẢN TIÊU CỰC]", "Kịch bản tiêu cực:"),
    "recommendation": ("[KHUYẾN NGHỊ]", "Khuyến nghị:"),
    "conclusion": ("[KẾT LUẬN]", "Kết luận:"),
}

_MARKET_SECTION_MARKERS = {
    "overview": ("[TỔNG QUAN]", "Tổng quan:"),
    "sentiment": ("[TÂM LÝ THỊ TRƯỜNG]", "Tâm lý thị trường:"),
    "positive_sectors": ("[NHÓM NGÀNH TÍCH CỰC]", "Nhóm ngành tích cực:"),
    "negative_sectors": ("[NHÓM NGÀNH TIÊU CỰC]", "Nhóm ngành tiêu cực:"),
    "cash_flow": ("[DÒNG TIỀN]", "Dòng tiền:"),
    "international_impact": ("[ẢNH HƯỞNG QUỐC TẾ]", "Ảnh hưởng quốc tế:"),
    "short_term": ("[NHẬN ĐỊNH NGẮN HẠN]", "Nhận định ngắn hạn:"),
    "medium_term": ("[NHẬN ĐỊNH TRUNG HẠN]", "Nhận định trung hạn:"),
    "risks": ("[RỦI RO CẦN THEO DÕI]", "Rủi ro cần theo dõi:"),
    "conclusion": ("[KẾT LUẬN]", "Kết luận:"),
}


class AnalysisService:
    """Build prompts, call the LLM, and parse structured analysis."""

    def __init__(
        self,
        llm: LLMProvider,
        prompt_builder: PromptBuilder,
        settings: AISettings,
        cache: AICache | None = None,
        market_prompt_builder: MarketPromptBuilder | None = None,
    ) -> None:
        self._llm = llm
        self._prompt_builder = prompt_builder
        self._settings = settings
        self._cache = cache
        self._logger = get_logger(__name__)
        self._market_prompt_builder = market_prompt_builder or MarketPromptBuilder(
            max_tokens=settings.max_tokens, temperature=settings.temperature
        )

    @property
    def is_configured(self) -> bool:
        """Return whether AI analysis can run."""
        return self._settings.enabled and self._settings.has_api_key

    async def analyze(self, context: AnalysisContext) -> StockAnalysisResult | None:
        """Run analysis for the given context."""
        if not self.is_configured:
            self._logger.info("ai_analysis_skipped", reason="disabled_or_missing_api_key")
            return None

        cache_key = _analysis_cache_key(context)
        cached = await self._get_cached_analysis(cache_key)
        if cached is not None:
            self._logger.info(
                "ai_analysis_cache_hit",
                symbol=context.symbol,
                mode=context.mode.value,
            )
            return cached

        request = self._prompt_builder.build(context)
        self._logger.info(
            "ai_prompt_built",
            symbol=context.symbol,
            mode=context.mode.value,
            prompt_length=len(request.prompt),
        )

        started = time.perf_counter()
        try:
            response = await self._llm.complete(request)
        except Exception as exc:
            self._logger.error(
                "ai_llm_failed",
                symbol=context.symbol,
                mode=context.mode.value,
                error=str(exc),
            )
            return None

        latency_ms = (time.perf_counter() - started) * 1000
        _log_response(self._logger, context, response, latency_ms)

        result = parse_analysis_response(
            symbol=context.symbol,
            content=response.content,
            mode=context.mode,
        )
        await self._set_cached_analysis(cache_key, result, response.content)
        return result

    async def analyze_market(self, context: MarketAnalysisContext) -> MarketAnalysisResult | None:
        """Run analysis for market context."""
        if not self.is_configured:
            self._logger.info("ai_analysis_skipped", reason="disabled_or_missing_api_key")
            return None

        cache_key = _market_analysis_cache_key(context)
        cached = await self._get_cached_market_analysis(cache_key)
        if cached is not None:
            self._logger.info("ai_market_analysis_cache_hit")
            return cached

        request = self._market_prompt_builder.build(context)
        self._logger.info("ai_market_prompt_built", prompt_length=len(request.prompt))

        started = time.perf_counter()
        try:
            response = await self._llm.complete(request)
        except Exception as exc:
            self._logger.error("ai_llm_failed", mode="market", error=str(exc))
            return None

        latency_ms = (time.perf_counter() - started) * 1000
        get_logger(__name__).info(
            "ai_llm_completed",
            mode="market",
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            latency_ms=round(latency_ms, 2),
            response_length=len(response.content),
        )

        result = parse_market_analysis_response(response.content)
        await self._set_cached_market_analysis(cache_key, result, response.content)
        return result

    async def _get_cached_analysis(self, cache_key: str) -> StockAnalysisResult | None:
        if self._cache is None:
            return None
        try:
            payload = await self._cache.get(cache_key)
        except Exception as exc:
            self._logger.warning("ai_analysis_cache_get_failed", error=str(exc))
            return None
        if payload is None:
            return None
        try:
            return analysis_result_from_json(payload)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    async def _set_cached_analysis(
        self,
        cache_key: str,
        result: StockAnalysisResult,
        raw_response: str,
    ) -> None:
        if self._cache is None:
            return
        try:
            await self._cache.set(
                cache_key,
                analysis_result_to_json(result),
                ttl_seconds=self._settings.cache_ttl_seconds,
            )
            await self._cache.set(
                f"ai_response:{cache_key}",
                raw_response,
                ttl_seconds=self._settings.cache_ttl_seconds,
            )
        except Exception as exc:
            self._logger.warning("ai_analysis_cache_set_failed", error=str(exc))

    async def _get_cached_market_analysis(self, cache_key: str) -> MarketAnalysisResult | None:
        if self._cache is None:
            return None
        try:
            payload = await self._cache.get(cache_key)
        except Exception as exc:
            self._logger.warning("ai_market_cache_get_failed", error=str(exc))
            return None
        if payload is None:
            return None
        try:
            data = json.loads(payload)
            data["sentiment"] = SentimentLabel(str(data.get("sentiment", SentimentLabel.NEUTRAL.value)))
            return MarketAnalysisResult(**data)
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            return None

    async def _set_cached_market_analysis(
        self,
        cache_key: str,
        result: MarketAnalysisResult,
        raw_response: str,
    ) -> None:
        if self._cache is None:
            return
        try:
            from dataclasses import asdict
            data = asdict(result)
            data["sentiment"] = result.sentiment.value
            await self._cache.set(
                cache_key,
                json.dumps(data, ensure_ascii=False),
                ttl_seconds=self._settings.cache_ttl_seconds,
            )
        except Exception as exc:
            self._logger.warning("ai_market_cache_set_failed", error=str(exc))


def _analysis_cache_key(context: AnalysisContext) -> str:
    news_fingerprint = "|".join(article.url for article in context.news)
    price_fingerprint = ""
    if context.price is not None:
        price_fingerprint = f"{context.price.current_price}:{context.price.change_percent}"
    historical_fingerprint = "|".join(
        f"{point.day}:{point.close}" for point in context.historical
    )
    digest = hashlib.sha256(
        f"{news_fingerprint}:{price_fingerprint}:{historical_fingerprint}".encode(),
    ).hexdigest()[:16]
    return f"analysis_result:{context.symbol}:{context.mode.value}:{digest}"


def _market_analysis_cache_key(context: MarketAnalysisContext) -> str:
    news_fingerprint = "|".join(article.url for article in context.news)
    indices_fingerprint = "|".join(
        f"{k}:{v.current_price if v else ''}" for k, v in context.indices.items()
    )
    sectors_fingerprint = "|".join(
        f"{k}:{v.current_price if v else ''}" for k, v in context.sectors.items()
    )
    digest = hashlib.sha256(
        f"{news_fingerprint}:{indices_fingerprint}:{sectors_fingerprint}".encode(),
    ).hexdigest()[:16]
    return f"market_analysis_result:{digest}"


def parse_analysis_response(
    symbol: str,
    content: str,
    mode: AnalysisMode,
) -> StockAnalysisResult:
    """Parse LLM output into a structured analysis result."""
    sections = _extract_sections(content)
    overview = sections.get("overview", "").strip() or content.strip()
    positives = sections.get("positives", "").strip() or "Chưa có đánh giá cụ thể."
    risks = sections.get("risks", "").strip() or "Chưa có rủi ro nổi bật."
    short_term = sections.get("short_term", "").strip() or "Theo dõi thêm diễn biến thị trường."
    
    recommendation_block = sections.get("recommendation", "")
    action = None
    confidence = None
    if "MUA" in recommendation_block.upper(): action = "MUA"
    elif "BÁN" in recommendation_block.upper() or "BAN" in recommendation_block.upper(): action = "BÁN"
    elif "GIỮ" in recommendation_block.upper() or "GIU" in recommendation_block.upper(): action = "GIỮ"
    elif "QUAN SÁT" in recommendation_block.upper() or "QUAN SAT" in recommendation_block.upper(): action = "QUAN SÁT"
    else: action = "KHÔNG RÕ"

    conf_match = re.search(r"(\d+)%", recommendation_block)
    if conf_match: confidence = conf_match.group(1) + "%"

    return StockAnalysisResult(
        symbol=symbol,
        overview=overview,
        positives=positives,
        risks=risks,
        short_term=short_term,
        sentiment=_infer_sentiment(overview, positives, risks),
        medium_term=sections.get("medium_term") if mode == AnalysisMode.FULL else None,
        conclusion=sections.get("conclusion") if mode == AnalysisMode.FULL else None,
        positive_scenario=sections.get("positive_scenario"),
        neutral_scenario=sections.get("neutral_scenario"),
        negative_scenario=sections.get("negative_scenario"),
        recommendation_action=action,
        recommendation_confidence=confidence,
        recommendation_reasons=recommendation_block,
        raw_response=content,
    )


def parse_market_analysis_response(content: str) -> MarketAnalysisResult:
    """Parse LLM output into structured market analysis result."""
    sections = _extract_sections(content, _MARKET_SECTION_MARKERS)
    overview = sections.get("overview", "").strip() or content.strip()
    positive_sectors = sections.get("positive_sectors", "").strip() or "Chưa có thông tin"
    negative_sectors = sections.get("negative_sectors", "").strip() or "Chưa có thông tin"
    
    return MarketAnalysisResult(
        overview=overview,
        sentiment=_infer_sentiment(overview, positive_sectors, negative_sectors),
        positive_sectors=positive_sectors,
        negative_sectors=negative_sectors,
        cash_flow=sections.get("cash_flow", "").strip() or "Chưa rõ",
        international_impact=sections.get("international_impact", "").strip() or "Chưa rõ",
        short_term=sections.get("short_term", "").strip() or "Theo dõi thêm",
        medium_term=sections.get("medium_term", "").strip() or "Chưa có đánh giá",
        risks=sections.get("risks", "").strip() or "Chưa có đánh giá",
        conclusion=sections.get("conclusion", "").strip() or "Chưa có kết luận",
        raw_response=content,
    )


def _extract_sections(content: str, markers_dict: dict[str, tuple[str, ...]] | None = None) -> dict[str, str]:
    if markers_dict is None:
        markers_dict = _SECTION_MARKERS
    normalized = content.replace("\r\n", "\n")
    markers: list[tuple[str, int]] = []
    for key, labels in markers_dict.items():
        for label in labels:
            match = re.search(re.escape(label), normalized, flags=re.IGNORECASE)
            if match is not None:
                markers.append((key, match.start()))
                break

    if not markers:
        return {}

    markers.sort(key=lambda item: item[1])
    sections: dict[str, str] = {}
    for index, (key, start) in enumerate(markers):
        label_end = normalized.find("\n", start)
        content_start = label_end + 1 if label_end != -1 else start
        content_end = markers[index + 1][1] if index + 1 < len(markers) else len(normalized)
        sections[key] = normalized[content_start:content_end].strip()
    return sections


def _infer_sentiment(overview: str, positives: str, risks: str) -> SentimentLabel:
    text = f"{overview} {positives} {risks}".lower()
    positive_hits = sum(
        1 for token in ("tích cực", "tăng", "lạc quan", "thuận lợi", "mạnh") if token in text
    )
    negative_hits = sum(
        1 for token in ("tiêu cực", "giảm", "rủi ro", "áp lực", "yếu") if token in text
    )
    if positive_hits > 0 and negative_hits > 0:
        return SentimentLabel.MIXED
    if positive_hits > negative_hits:
        return SentimentLabel.POSITIVE
    if negative_hits > positive_hits:
        return SentimentLabel.NEGATIVE
    return SentimentLabel.NEUTRAL


def _log_response(logger: object, context: AnalysisContext, response: LLMResponse, latency_ms: float) -> None:
    get_logger(__name__).info(
        "ai_llm_completed",
        symbol=context.symbol,
        mode=context.mode.value,
        model=response.model,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        latency_ms=round(latency_ms, 2),
        response_length=len(response.content),
    )
