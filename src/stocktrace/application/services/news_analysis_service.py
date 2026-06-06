"""News sentiment analysis service."""

from __future__ import annotations

from dataclasses import dataclass

from stocktrace.application.services.market_data import NewsArticle

_POSITIVE_KEYWORDS = (
    "tăng",
    "lãi",
    "kỷ lục",
    "ky luc",
    "tích cực",
    "tich cuc",
    "vượt",
    "vuot",
    "mạnh",
    "manh",
    "thuận lợi",
    "thuan loi",
    "buy",
    "upgrade",
    "beat",
    "growth",
    "profit",
)

_NEGATIVE_KEYWORDS = (
    "giảm",
    "giam",
    "lỗ",
    "lo",
    "tiêu cực",
    "tieu cuc",
    "sụt",
    "sut",
    "yếu",
    "yeu",
    "downgrade",
    "loss",
    "decline",
    "risk",
    "investigation",
    "scandal",
)


@dataclass(frozen=True, slots=True)
class NewsSentimentResult:
    """Aggregated news sentiment for a symbol."""

    label: str
    positive_count: int
    negative_count: int
    neutral_count: int
    headline_summary: str


class NewsAnalysisService:
    """Evaluate sentiment from recent news headlines."""

    def analyze(self, articles: list[NewsArticle], limit: int = 5) -> NewsSentimentResult:
        """Return sentiment label and headline summary from recent articles."""
        selected = articles[:limit]
        if not selected:
            return NewsSentimentResult(
                label="Trung lập",
                positive_count=0,
                negative_count=0,
                neutral_count=0,
                headline_summary="Không có tin tức gần đây.",
            )

        positive = 0
        negative = 0
        neutral = 0
        headlines: list[str] = []

        for article in selected:
            text = f"{article.title} {article.summary or ''}".lower()
            is_positive = any(keyword in text for keyword in _POSITIVE_KEYWORDS)
            is_negative = any(keyword in text for keyword in _NEGATIVE_KEYWORDS)

            if is_positive and not is_negative:
                positive += 1
            elif is_negative and not is_positive:
                negative += 1
            else:
                neutral += 1
            headlines.append(article.title)

        if positive > negative and positive >= neutral:
            label = "Tích cực"
        elif negative > positive and negative >= neutral:
            label = "Tiêu cực"
        elif positive > 0 and negative > 0:
            label = "Hỗn hợp"
        else:
            label = "Trung lập"

        return NewsSentimentResult(
            label=label,
            positive_count=positive,
            negative_count=negative,
            neutral_count=neutral,
            headline_summary=" | ".join(headlines[:3]),
        )
