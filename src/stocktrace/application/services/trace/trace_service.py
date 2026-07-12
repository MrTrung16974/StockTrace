"""Trace engine application service."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from stocktrace.application.services.financial.financial_analysis_service import (
    FinancialAnalysisService,
)
from stocktrace.application.services.trace.scoring_engine import TraceScoringEngine
from stocktrace.application.services.trace.source_catalog import official_trace_sources
from stocktrace.domain.entities.trace import (
    StockTraceEvent,
    TraceEventType,
    TraceExplanation,
    TraceReason,
    TraceSeverity,
    TraceSource,
    TraceSourceType,
    TraceTimeline,
)
from stocktrace.domain.ports.financial_provider import FinancialDataNotFoundError
from stocktrace.domain.repositories.trace import TraceEventRepository, TraceSourceRepository
from stocktrace.domain.value_objects.financial_period import FinancialPeriod


class TraceRepository(TraceEventRepository, TraceSourceRepository, Protocol):
    """Combined repository contract needed by the trace service."""


TraceRepositoryFactory = Callable[[], AbstractAsyncContextManager[TraceRepository]]

_FINANCIAL_FALLBACK_SOURCE = TraceSource(
    code="STFIN",
    name="StockTrace Financial Engine",
    source_type=TraceSourceType.THIRD_PARTY,
    base_url="stocktrace://financial-analysis",
    rank=3,
    official=False,
    description=(
        "Internal financial signal derived from configured financial providers. "
        "Use as a trace fallback until official disclosures are ingested."
    ),
)


class TraceService:
    """Coordinate trace source seeding, timeline retrieval, and scoring."""

    def __init__(
        self,
        repository_context_factory: TraceRepositoryFactory,
        financial_analysis_service: FinancialAnalysisService | None = None,
        scoring_engine: TraceScoringEngine | None = None,
    ) -> None:
        self._repository_context_factory = repository_context_factory
        self._financial_analysis_service = financial_analysis_service
        self._scoring = scoring_engine or TraceScoringEngine()

    async def seed_official_sources(self) -> None:
        """Seed official source metadata."""
        async with self._repository_context_factory() as repository:
            for source in official_trace_sources():
                await repository.upsert_source(source)

    async def save_event(self, event: StockTraceEvent) -> None:
        """Persist a normalized trace event."""
        async with self._repository_context_factory() as repository:
            await repository.save_event(event)

    async def build_timeline(
        self,
        symbol: str,
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> TraceTimeline:
        """Return scored trace timeline for a stock symbol."""
        normalized = symbol.strip().upper()
        async with self._repository_context_factory() as repository:
            events = tuple(
                await repository.list_events(symbol=normalized, since=since, limit=limit),
            )

        if not events and self._financial_analysis_service is not None:
            events = await self._build_financial_fallback_events(normalized)

        score = self._scoring.calculate(normalized, events)
        return TraceTimeline(symbol=normalized, events=events, score=score)

    async def list_recent_events(
        self,
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> tuple[StockTraceEvent, ...]:
        """Return recent trace events across the market."""
        async with self._repository_context_factory() as repository:
            return tuple(await repository.list_events(since=since, limit=limit))

    async def explain(
        self,
        symbol: str,
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> TraceExplanation:
        """Return deterministic explanation for why a symbol is being traced."""
        timeline = await self.build_timeline(symbol, since=since, limit=limit)
        score = timeline.score

        if not timeline.events:
            return TraceExplanation(
                symbol=timeline.symbol,
                summary=(
                    "Chưa có sự kiện trace đã ingest từ nguồn công bố chính thống cho mã này."
                ),
                reasons=(),
                risks=(),
                next_watch=(
                    "Theo dõi công bố doanh nghiệp trên HOSE/HNX/UPCoM.",
                    "Đối chiếu sự kiện quyền tại VSDC.",
                    "Theo dõi cảnh báo/quy định từ SSC và văn bản liên quan từ MOF.",
                ),
                confidence=score.conviction_score,
            )

        reasons = tuple(
            f"{event.title} ({event.source.code})"
            for event in timeline.events[:5]
        )
        risks = tuple(
            f"{event.title} ({event.severity.value})"
            for event in timeline.events
            if event.severity in (TraceSeverity.MEDIUM, TraceSeverity.HIGH, TraceSeverity.CRITICAL)
        )[:5]
        next_watch = tuple(
            sorted({event.event_type.value for event in timeline.events})
        )[:5]

        summary = (
            f"{timeline.symbol} có {score.event_count} tín hiệu trace, "
            f"điểm tín hiệu {score.signal_score}/100 và rủi ro {score.risk_score}/100."
        )

        return TraceExplanation(
            symbol=timeline.symbol,
            summary=summary,
            reasons=reasons,
            risks=risks,
            next_watch=next_watch,
            confidence=score.conviction_score,
        )

    async def _build_financial_fallback_events(self, symbol: str) -> tuple[StockTraceEvent, ...]:
        """Build temporary trace events from financial analysis when no source event exists."""
        if self._financial_analysis_service is None:
            return ()

        try:
            dashboard = await self._financial_analysis_service.analyze(
                symbol,
                FinancialPeriod.parse("1Y"),
            )
        except FinancialDataNotFoundError:
            return ()

        analysis = dashboard.analysis
        score = analysis.score
        valuation = analysis.valuation
        latest = analysis.ratios[-1] if analysis.ratios else None

        financial_reasons = (
            TraceReason(
                label="Điểm tài chính",
                detail=f"{score.overall_score}/10, khuyến nghị {score.recommendation.value}.",
                weight=Decimal("1"),
            ),
            TraceReason(
                label="Tăng trưởng",
                detail=f"Nhóm tăng trưởng đạt {score.growth_score}/10.",
                weight=Decimal("0.8"),
            ),
            TraceReason(
                label="Dòng tiền",
                detail=f"Nhóm dòng tiền đạt {score.cash_flow_score}/10.",
                weight=Decimal("0.8"),
            ),
        )

        events = [
            StockTraceEvent(
                symbol=symbol,
                event_type=TraceEventType.TRACE_FINANCIAL_STATEMENT,
                severity=self._severity_from_score(score.overall_score),
                title=f"Điểm tài chính {symbol}: {score.overall_score}/10",
                summary=(
                    "Tín hiệu tạm sinh từ Financial Analysis Engine; cần đối chiếu với "
                    "báo cáo tài chính và công bố doanh nghiệp chính thức."
                ),
                source=_FINANCIAL_FALLBACK_SOURCE,
                reasons=financial_reasons,
                confidence=Decimal("0.70"),
                metadata={"fallback": "financial_analysis"},
            ),
            StockTraceEvent(
                symbol=symbol,
                event_type=TraceEventType.TRACE_FINANCIAL_STATEMENT,
                severity=TraceSeverity.INFO,
                title=f"Định giá {symbol}: {valuation.status.value}",
                summary=(
                    f"PE hiện tại {valuation.current_pe or 'N/A'}, "
                    f"PE trung bình {valuation.average_pe or 'N/A'}."
                ),
                source=_FINANCIAL_FALLBACK_SOURCE,
                reasons=(
                    TraceReason(
                        label="Định giá",
                        detail=f"Trạng thái định giá: {valuation.status.value}.",
                        weight=Decimal("0.7"),
                    ),
                ),
                confidence=Decimal("0.65"),
                metadata={"fallback": "financial_analysis"},
            ),
        ]

        if latest is not None:
            events.append(
                StockTraceEvent(
                    symbol=symbol,
                    event_type=TraceEventType.TRACE_FINANCIAL_STATEMENT,
                    severity=(
                        TraceSeverity.MEDIUM
                        if score.debt_score < Decimal("5")
                        else TraceSeverity.INFO
                    ),
                    title=f"Nợ và dòng tiền {symbol}",
                    summary=(
                        f"Nợ/VCSH {latest.debt_to_equity or 'N/A'}, "
                        f"dòng tiền tự do {latest.free_cash_flow or 'N/A'}."
                    ),
                    source=_FINANCIAL_FALLBACK_SOURCE,
                    reasons=(
                        TraceReason(
                            label="Đòn bẩy",
                            detail=f"Điểm nợ đạt {score.debt_score}/10.",
                            weight=Decimal("0.7"),
                        ),
                        TraceReason(
                            label="Dòng tiền",
                            detail=f"Điểm dòng tiền đạt {score.cash_flow_score}/10.",
                            weight=Decimal("0.7"),
                        ),
                    ),
                    confidence=Decimal("0.65"),
                    metadata={"fallback": "financial_analysis"},
                ),
            )

        return tuple(events)

    def _severity_from_score(self, score: Decimal) -> TraceSeverity:
        if score >= Decimal("7"):
            return TraceSeverity.INFO
        if score >= Decimal("5"):
            return TraceSeverity.LOW
        if score >= Decimal("3"):
            return TraceSeverity.MEDIUM
        return TraceSeverity.HIGH
