from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class NewsArticle:
    """Immutable domain entity representing a news article for a stock."""

    title: str
    url: str
    source: str
    symbol: str
    published_at: datetime
    summary: Optional[str] = None
    thumbnail: Optional[str] = None
    fetched_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def age_label(self) -> str:
        """Human-readable age of the article."""
        delta = datetime.utcnow() - self.published_at
        minutes = int(delta.total_seconds() / 60)
        if minutes < 60:
            return f"{minutes} phút trước"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} giờ trước"
        days = hours // 24
        return f"{days} ngày trước"
