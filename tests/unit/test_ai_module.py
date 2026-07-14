"""Unit tests for the AI analysis module."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import SecretStr

from stocktrace.ai.analysis_service import AnalysisService, parse_analysis_response
from stocktrace.ai.models import (
    AnalysisContext,
    AnalysisMode,
    HistoricalPoint,
    LLMRequest,
    LLMResponse,
    SentimentLabel,
)
from stocktrace.ai.prompt_builder import PromptBuilder
from stocktrace.ai.serialization import analysis_result_from_json, analysis_result_to_json
from stocktrace.ai.translation_service import TranslationService, _parse_translation_response
from stocktrace.application.services.market_data import NewsArticle, StockQuote
from stocktrace.application.services.stock_analysis_service import AnalysisBundle
from stocktrace.infrastructure.cache.memory_ai_cache import InMemoryAICache
from stocktrace.infrastructure.config.settings import AISettings
from stocktrace.infrastructure.telegram.messages import (
    append_ai_news_section,
    build_ai_news_section,
    build_full_analysis_message,
)


class FakeLLM:
    """LLM provider test double."""

    def __init__(self, content: str) -> None:
        self.content = content
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(
            content=self.content,
            model="fake-model",
            latency_ms=12.5,
            prompt_tokens=100,
            completion_tokens=50,
        )


def _ai_settings(*, enabled: bool = True, translate_news: bool = True) -> AISettings:
    return AISettings(
        enabled=enabled,
        api_key=SecretStr("test-key"),
        translate_news=translate_news,
        cache_ttl_seconds=1800,
    )


def _sample_quote() -> StockQuote:
    return StockQuote(
        ticker="VCB",
        company_name="Vietcombank",
        current_price=Decimal("98500"),
        change=Decimal("2200"),
        change_percent=Decimal("2.3"),
        open_price=Decimal("96000"),
        high_price=Decimal("99000"),
        low_price=Decimal("95500"),
        volume=1000000,
        timestamp=datetime.now(tz=UTC),
        currency="VND",
        source="VNDIRECT",
    )


def _sample_articles() -> tuple[NewsArticle, ...]:
    return (
        NewsArticle(
            ticker="VCB",
            title="Vietcombank reports strong earnings",
            summary="Profit growth continues.",
            url="https://example.com/vcb-1",
            source="Reuters",
        ),
    )


def test_prompt_builder_news_only_includes_sections() -> None:
    builder = PromptBuilder()
    prompt = builder.build(
        AnalysisContext(
            symbol="VCB",
            news=_sample_articles(),
            mode=AnalysisMode.NEWS_ONLY,
            price=_sample_quote(),
        ),
    ).prompt

    assert "VCB" in prompt
    assert "[TỔNG QUAN]" in prompt
    assert "Vietcombank reports strong earnings" in prompt
    assert "Không khuyến nghị mua bán tuyệt đối" in prompt


def test_prompt_builder_full_includes_historical() -> None:
    builder = PromptBuilder()
    prompt = builder.build(
        AnalysisContext(
            symbol="VCB",
            news=_sample_articles(),
            mode=AnalysisMode.FULL,
            price=_sample_quote(),
            historical=(
                HistoricalPoint(
                    day=date(2026, 6, 1),
                    close=Decimal("96000"),
                    change_percent=Decimal("1.1"),
                ),
            ),
        ),
    ).prompt

    assert "[ĐÁNH GIÁ TRUNG HẠN]" in prompt
    assert "Phân tích Kỹ thuật:" in prompt


def test_parse_analysis_response_extracts_sections() -> None:
    content = "\n".join(
        [
            "[TỔNG QUAN]",
            "Thị trường ổn định.",
            "[ĐIỂM TÍCH CỰC]",
            "Lợi nhuận tăng.",
            "[RỦI RO]",
            "Biến động lãi suất.",
            "[ĐÁNH GIÁ NGẮN HẠN]",
            "Xu hướng tích cực.",
            "[ĐÁNH GIÁ TRUNG HẠN]",
            "Triển vọng khả quan.",
            "[KẾT LUẬN]",
            "Theo dõi thêm.",
        ],
    )

    result = parse_analysis_response("VCB", content, AnalysisMode.FULL)

    assert result.overview == "Thị trường ổn định."
    assert result.positives == "Lợi nhuận tăng."
    assert result.medium_term == "Triển vọng khả quan."
    assert result.conclusion == "Theo dõi thêm."
    assert result.sentiment in {SentimentLabel.POSITIVE, SentimentLabel.MIXED}


@pytest.mark.asyncio
async def test_analysis_service_uses_cache() -> None:
    llm = FakeLLM(
        "\n".join(
            [
                "[TỔNG QUAN]",
                "Ổn định.",
                "[ĐIỂM TÍCH CỰC]",
                "Tốt.",
                "[RỦI RO]",
                "Thấp.",
                "[ĐÁNH GIÁ NGẮN HẠN]",
                "Tăng nhẹ.",
            ],
        ),
    )
    cache = InMemoryAICache()
    service = AnalysisService(
        llm=llm,
        prompt_builder=PromptBuilder(),
        settings=_ai_settings(),
        cache=cache,
    )
    context = AnalysisContext(
        symbol="VCB",
        news=_sample_articles(),
        mode=AnalysisMode.NEWS_ONLY,
        price=_sample_quote(),
    )

    first = await service.analyze(context)
    second = await service.analyze(context)

    assert first is not None
    assert second is not None
    assert first.overview == "Ổn định."
    assert len(llm.requests) == 1


@pytest.mark.asyncio
async def test_analysis_service_returns_none_when_disabled() -> None:
    service = AnalysisService(
        llm=FakeLLM("ignored"),
        prompt_builder=PromptBuilder(),
        settings=_ai_settings(enabled=False),
    )
    result = await service.analyze(
        AnalysisContext(symbol="VCB", news=_sample_articles(), mode=AnalysisMode.NEWS_ONLY),
    )
    assert result is None


@pytest.mark.asyncio
async def test_translation_service_parses_json_response() -> None:
    llm = FakeLLM(
        '[{"index": 1, "title_vi": "Vietcombank báo cáo lợi nhuận", "summary_vi": "Tăng trưởng"}]',
    )
    service = TranslationService(llm=llm, settings=_ai_settings(), cache=InMemoryAICache())
    articles = [
        NewsArticle(
            ticker="VCB",
            title="Vietcombank reports earnings",
            summary="Growth",
            url="https://example.com/a",
            source="Reuters",
        ),
    ]

    translated = await service.translate_articles("VCB", articles)

    assert translated[0].title == "Vietcombank báo cáo lợi nhuận"
    assert translated[0].summary == "Tăng trưởng"


def test_parse_translation_response_handles_array() -> None:
    parsed = _parse_translation_response(
        'Result: [{"index": 1, "title_vi": "Tiêu đề", "summary_vi": "Mô tả"}]',
        1,
    )
    assert parsed[0]["title_vi"] == "Tiêu đề"


def test_analysis_result_json_roundtrip() -> None:
    result = parse_analysis_response(
        "VCB",
        "\n".join(
            [
                "[TỔNG QUAN]",
                "OK",
                "[ĐIỂM TÍCH CỰC]",
                "Good",
                "[RỦI RO]",
                "Low",
                "[ĐÁNH GIÁ NGẮN HẠN]",
                "Up",
            ],
        ),
        AnalysisMode.NEWS_ONLY,
    )
    restored = analysis_result_from_json(analysis_result_to_json(result))
    assert restored.symbol == "VCB"
    assert restored.overview == "OK"


def test_build_ai_news_section_format() -> None:
    result = parse_analysis_response(
        "VCB",
        "\n".join(
            [
                "[TỔNG QUAN]",
                "Tổng quan test",
                "[ĐIỂM TÍCH CỰC]",
                "Tích cực test",
                "[RỦI RO]",
                "Rủi ro test",
                "[ĐÁNH GIÁ NGẮN HẠN]",
                "Ngắn hạn test",
            ],
        ),
        AnalysisMode.NEWS_ONLY,
    )
    section = build_ai_news_section(result)
    assert "🤖 PHÂN TÍCH AI" in section
    assert "Tổng quan test" in section
    assert "Ngắn hạn test" in section


def test_append_ai_news_section_preserves_original_news() -> None:
    original = "News for VCB:\n1. <a href=\"https://x.com\">Title</a>"
    result = parse_analysis_response(
        "VCB",
        "[TỔNG QUAN]\nA\n[ĐIỂM TÍCH CỰC]\nB\n[RỦI RO]\nC\n[ĐÁNH GIÁ NGẮN HẠN]\nD",
        AnalysisMode.NEWS_ONLY,
    )
    combined = append_ai_news_section(original, result)
    assert combined.startswith(original)
    assert "🤖 PHÂN TÍCH AI" in combined


def test_build_full_analysis_message_includes_price_and_ai() -> None:
    analysis = parse_analysis_response(
        "VCB",
        "\n".join(
            [
                "[TỔNG QUAN]",
                "Tổng quan",
                "[ĐIỂM TÍCH CỰC]",
                "Mạnh",
                "[RỦI RO]",
                "Thấp",
                "[ĐÁNH GIÁ NGẮN HẠN]",
                "Tăng",
                "[ĐÁNH GIÁ TRUNG HẠN]",
                "Ổn",
                "[KẾT LUẬN]",
                "Theo dõi",
            ],
        ),
        AnalysisMode.FULL,
    )
    message = build_full_analysis_message(
        AnalysisBundle(
            symbol="VCB",
            quote=_sample_quote(),
            news=_sample_articles(),
            analysis=analysis,
        ),
    )

    assert "BÁO CÁO PHÂN TÍCH CỔ PHIẾU VCB" in message
    assert "98.500" in message
    assert "+2,3%" in message or "+2.3%" in message
    assert "NHẬN ĐỊNH AI" in message
    assert "KHUYẾN NGHỊ" in message
