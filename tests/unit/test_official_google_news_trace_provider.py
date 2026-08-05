"""Tests for official-source trace ingestion through Google News RSS."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from email.utils import format_datetime

import pytest
import respx
from httpx import Response

from stocktrace.domain.entities.trace import TraceEventType, TraceSeverity
from stocktrace.infrastructure.providers.official_google_news import OfficialGoogleNewsTraceProvider


@pytest.mark.asyncio
@respx.mock
async def test_provider_keeps_only_recognized_official_publishers() -> None:
    published_at = format_datetime(datetime.now(tz=UTC))
    respx.get("https://news.google.com/rss/search").mock(
        return_value=Response(
            200,
            text=f"""<?xml version="1.0"?>
            <rss version="2.0"><channel>
              <item>
                <title>HPG: Chốt danh sách trả cổ tức</title>
                <link>https://news.google.com/rss/articles/hpg-official</link>
                <source>Sở Giao dịch Chứng khoán TP Hồ Chí Minh</source>
                <pubDate>{published_at}</pubDate>
              </item>
              <item>
                <title>HPG outlook</title>
                <link>https://example.com/hpg</link>
                <source>Unverified Blog</source>
                <pubDate>{published_at}</pubDate>
              </item>
            </channel></rss>""",
        ),
    )

    events = await OfficialGoogleNewsTraceProvider(timeout_seconds=1).list_events(
        symbol="HPG",
        limit=10,
    )

    assert len(events) == 1
    event = events[0]
    assert event.source.code == "HOSE"
    assert event.event_type == TraceEventType.TRACE_CORPORATE_ACTION
    assert event.severity == TraceSeverity.INFO
    assert event.confidence == Decimal("1")
