"""Official Vietnamese market-disclosure ingestion through Google News RSS."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import ssl
from time import struct_time
from typing import Any, cast

import feedparser
import httpx

from stocktrace.application.services.trace.source_catalog import official_trace_sources
from stocktrace.domain.entities.trace import (
    StockTraceEvent,
    TraceDocument,
    TraceEventType,
    TraceSeverity,
    TraceSource,
)
from stocktrace.domain.ports.official_source_provider import OfficialSourceProviderError

_GOOGLE_NEWS_URL = "https://news.google.com/rss/search"
_OFFICIAL_DOMAINS = (
    "vsd.vn",
    "hsx.vn",
    "hnx.vn",
    "ssc.gov.vn",
    "vnx.vn",
    "mof.gov.vn",
    "sbv.gov.vn",
)
_SOURCE_MATCHERS = {
    "VSDC": ("vsdc", "lưu ký", "depository"),
    "HOSE": ("hose", "hsx", "hồ chí minh", "ho chi minh"),
    "HNX": ("hnx", "hà nội", "ha noi"),
    "SSC": ("ssc", "ủy ban chứng khoán", "uy ban chung khoan"),
    "VNX": ("vnx", "sở giao dịch chứng khoán việt nam"),
    "MOF": ("mof", "bộ tài chính", "bo tai chinh"),
    "SBV": ("sbv", "ngân hàng nhà nước", "ngan hang nha nuoc"),
}
_HIGH_RISK = ("đình chỉ", "dinh chi", "hủy niêm yết", "huy niem yet", "xử phạt", "xu phat")
_MEDIUM_RISK = ("cảnh báo", "canh bao", "kiểm soát", "kiem soat", "hạn chế", "han che")
_CORPORATE_ACTION = ("cổ tức", "co tuc", "quyền", "quyen", "chốt danh sách", "dai hoi")
_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}


class OfficialGoogleNewsTraceProvider:
    """Retrieve recent official Vietnamese market notices from a public RSS feed."""

    def __init__(
        self,
        timeout_seconds: float,
        ca_bundle_path: str | None = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._ssl_context = (
            ssl.create_default_context(cafile=ca_bundle_path) if ca_bundle_path is not None else None
        )
        self._sources = {source.code: source for source in official_trace_sources()}

    @property
    def provider_name(self) -> str:
        return "official-google-news"

    @property
    def source(self) -> TraceSource:
        return self._sources["VNX"]

    async def list_events(
        self,
        *,
        symbol: str | None = None,
        event_types: tuple[TraceEventType, ...] = (),
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[StockTraceEvent]:
        """Return notices whose publisher maps to an official trace source."""
        if symbol is None:
            return []
        normalized = symbol.strip().upper()
        try:
            async with self._client() as client:
                response = await client.get(
                    _GOOGLE_NEWS_URL,
                    params={"q": _query(normalized), "hl": "vi", "gl": "VN", "ceid": "VN:vi"},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            msg = f"Official news fetch failed for {normalized}: {exc}"
            raise OfficialSourceProviderError(msg) from exc

        events = _parse_events(response.text, normalized, self._sources)
        if since is not None:
            events = [event for event in events if (event.occurred_at or event.created_at) >= since]
        if event_types:
            events = [event for event in events if event.event_type in event_types]
        return events[:limit]

    async def fetch_document(self, url: str) -> TraceDocument:
        """Fetch an RSS-linked source document for audit retention."""
        try:
            async with self._client() as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            msg = f"Official document fetch failed: {exc}"
            raise OfficialSourceProviderError(msg) from exc
        return TraceDocument(
            source_code=self.source.code,
            title=url,
            url=url,
            raw_text=response.text,
        )

    def _client(self) -> httpx.AsyncClient:
        """Create a TLS-verifying client, optionally using an explicit enterprise CA."""
        return httpx.AsyncClient(
            timeout=self._timeout_seconds,
            verify=self._ssl_context if self._ssl_context is not None else True,
            headers=_HTTP_HEADERS,
            follow_redirects=True,
        )


def _query(symbol: str) -> str:
    domains = " OR ".join(f"site:{domain}" for domain in _OFFICIAL_DOMAINS)
    return f'("{symbol}" OR "HOSE:{symbol}") ({domains}) when:45d'


def _parse_events(
    raw_feed: str,
    symbol: str,
    sources: dict[str, TraceSource],
) -> list[StockTraceEvent]:
    entries = cast(list[dict[str, Any]], feedparser.parse(raw_feed).entries)
    events: list[StockTraceEvent] = []
    for entry in entries:
        title = str(entry.get("title") or "").strip()
        url = str(entry.get("link") or "").strip()
        publisher = _publisher(entry.get("source"))
        source = _official_source(publisher, sources)
        if not title or not url or source is None:
            continue
        published_at = _published_at(entry.get("published_parsed"))
        events.append(
            StockTraceEvent(
                symbol=symbol,
                event_type=_event_type(title),
                severity=_severity(title),
                title=title,
                summary=f"Công bố từ {source.name}.",
                source=source,
                document=TraceDocument(
                    source_code=source.code,
                    title=title,
                    url=url,
                    published_at=published_at,
                ),
                confidence=_confidence(source.code),
                occurred_at=published_at,
                metadata={"ingestion_provider": "official-google-news", "publisher": publisher},
            ),
        )
    return events


def _publisher(value: object) -> str:
    return str(value.get("title") or "") if isinstance(value, dict) else str(value or "")


def _official_source(publisher: str, sources: dict[str, TraceSource]) -> TraceSource | None:
    normalized = publisher.lower()
    for code, matchers in _SOURCE_MATCHERS.items():
        if any(matcher in normalized for matcher in matchers):
            return sources[code]
    return None


def _published_at(value: object) -> datetime | None:
    if not isinstance(value, struct_time):
        return None
    return datetime(*value[:6], tzinfo=UTC)


def _event_type(title: str) -> TraceEventType:
    normalized = title.lower()
    if any(marker in normalized for marker in _CORPORATE_ACTION):
        return TraceEventType.TRACE_CORPORATE_ACTION
    if any(marker in normalized for marker in _HIGH_RISK + _MEDIUM_RISK):
        return TraceEventType.TRACE_REGULATORY
    return TraceEventType.TRACE_DISCLOSURE


def _severity(title: str) -> TraceSeverity:
    normalized = title.lower()
    if any(marker in normalized for marker in _HIGH_RISK):
        return TraceSeverity.HIGH
    if any(marker in normalized for marker in _MEDIUM_RISK):
        return TraceSeverity.MEDIUM
    return TraceSeverity.INFO


def _confidence(source_code: str) -> Decimal:
    return {
        "HOSE": Decimal("1"),
        "HNX": Decimal("1"),
        "VSDC": Decimal("1"),
        "SSC": Decimal("1"),
    }.get(source_code, Decimal("0.9"))
