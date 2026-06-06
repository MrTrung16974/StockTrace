"""AI-powered news translation."""

from __future__ import annotations

import hashlib
import json
import re
import time

from stocktrace.ai.models import LLMRequest
from stocktrace.application.services.market_data import NewsArticle
from stocktrace.domain.ports.ai_cache import AICache
from stocktrace.domain.ports.llm_provider import LLMProvider
from stocktrace.infrastructure.config.settings import AISettings
from stocktrace.infrastructure.logging.config import get_logger

_TRANSLATION_SYSTEM = (
    "Bạn là trợ lý dịch tin tức tài chính. "
    "Luôn trả về JSON hợp lệ theo định dạng được yêu cầu."
)


class TranslationService:
    """Translate news titles and summaries to Vietnamese via LLM."""

    def __init__(
        self,
        llm: LLMProvider,
        settings: AISettings,
        cache: AICache | None = None,
    ) -> None:
        self._llm = llm
        self._settings = settings
        self._cache = cache
        self._logger = get_logger(__name__)

    @property
    def is_configured(self) -> bool:
        """Return whether translation can run."""
        return self._settings.enabled and self._settings.translate_news and self._settings.has_api_key

    async def translate_articles(
        self,
        symbol: str,
        articles: list[NewsArticle],
    ) -> list[NewsArticle]:
        """Return articles with Vietnamese titles and summaries when possible."""
        if not self.is_configured or not articles:
            return articles

        results: list[NewsArticle | None] = [None] * len(articles)
        uncached: list[tuple[int, NewsArticle]] = []

        for index, article in enumerate(articles):
            cached = await self._get_cached_translation(article)
            if cached is not None:
                results[index] = cached
            else:
                uncached.append((index, article))

        if uncached:
            batch_results = await self._translate_batch(
                symbol,
                [article for _, article in uncached],
            )
            for (index, original), translated_fields in zip(uncached, batch_results, strict=True):
                translated = NewsArticle(
                    ticker=original.ticker,
                    title=translated_fields.get("title_vi") or original.title,
                    summary=translated_fields.get("summary_vi") or original.summary,
                    url=original.url,
                    source=original.source,
                    published_at=original.published_at,
                )
                await self._set_cached_translation(original, translated)
                results[index] = translated

        return [article for article in results if article is not None]

    async def _translate_batch(
        self,
        symbol: str,
        articles: list[NewsArticle],
    ) -> list[dict[str, str | None]]:
        items = []
        for index, article in enumerate(articles, start=1):
            items.append(
                {
                    "index": index,
                    "title": article.title,
                    "summary": article.summary or "",
                },
            )

        prompt = "\n".join(
            [
                f'Dịch tin tức liên quan đến mã "{symbol}" sang tiếng Việt.',
                "QUY TẮC:",
                f"- KHÔNG dịch mã cổ phiếu ({symbol}).",
                "- KHÔNG dịch tên doanh nghiệp (ví dụ Vietcombank giữ nguyên Vietcombank).",
                "- Trả về JSON array duy nhất, mỗi phần tử: "
                '{"index": 1, "title_vi": "...", "summary_vi": "..."}',
                "",
                "Dữ liệu:",
                json.dumps(items, ensure_ascii=False),
            ],
        )
        request = LLMRequest(
            prompt=prompt,
            max_tokens=1024,
            temperature=0.1,
            system_prompt=_TRANSLATION_SYSTEM,
        )

        started = time.perf_counter()
        try:
            response = await self._llm.complete(request)
        except Exception as exc:
            self._logger.error("ai_translation_failed", symbol=symbol, error=str(exc))
            return [{"title_vi": article.title, "summary_vi": article.summary} for article in articles]

        latency_ms = (time.perf_counter() - started) * 1000
        self._logger.info(
            "ai_translation_completed",
            symbol=symbol,
            articles_count=len(articles),
            prompt_length=len(prompt),
            latency_ms=round(latency_ms, 2),
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
        )
        return _parse_translation_response(response.content, len(articles))

    async def _get_cached_translation(self, article: NewsArticle) -> NewsArticle | None:
        if self._cache is None:
            return None
        key = _translation_cache_key(article.url)
        try:
            payload = await self._cache.get(key)
        except Exception:
            return None
        if payload is None:
            return None
        data = json.loads(payload)
        return NewsArticle(
            ticker=article.ticker,
            title=str(data.get("title_vi") or article.title),
            summary=data.get("summary_vi") or article.summary,
            url=article.url,
            source=article.source,
            published_at=article.published_at,
        )

    async def _set_cached_translation(self, original: NewsArticle, translated: NewsArticle) -> None:
        if self._cache is None:
            return
        key = _translation_cache_key(original.url)
        payload = json.dumps(
            {"title_vi": translated.title, "summary_vi": translated.summary},
            ensure_ascii=False,
        )
        try:
            await self._cache.set(key, payload, ttl_seconds=self._settings.cache_ttl_seconds)
        except Exception as exc:
            self._logger.warning("ai_translation_cache_set_failed", error=str(exc))


def _translation_cache_key(url: str) -> str:
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    return f"news_translation:{digest}"


def _parse_translation_response(content: str, expected_count: int) -> list[dict[str, str | None]]:
    match = re.search(r"\[[\s\S]*\]", content)
    if match is None:
        return [{"title_vi": None, "summary_vi": None} for _ in range(expected_count)]

    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return [{"title_vi": None, "summary_vi": None} for _ in range(expected_count)]

    if not isinstance(parsed, list):
        return [{"title_vi": None, "summary_vi": None} for _ in range(expected_count)]

    by_index: dict[int, dict[str, str | None]] = {}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        if not isinstance(index, int):
            continue
        by_index[index] = {
            "title_vi": str(item["title_vi"]) if item.get("title_vi") else None,
            "summary_vi": str(item["summary_vi"]) if item.get("summary_vi") else None,
        }

    return [
        by_index.get(index, {"title_vi": None, "summary_vi": None})
        for index in range(1, expected_count + 1)
    ]
