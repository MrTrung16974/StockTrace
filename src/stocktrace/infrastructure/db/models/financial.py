"""Financial analysis ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from stocktrace.infrastructure.db.base import Base


class FinancialStatementModel(Base):
    """Persisted financial statement snapshot."""

    __tablename__ = "financial_statements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(16), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    statement_type: Mapped[str] = mapped_column(String(32), nullable=False)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="mock")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_financial_statements_symbol_period", "symbol", "period"),
    )


class FinancialRatioModel(Base):
    """Persisted financial ratio calculations."""

    __tablename__ = "financial_ratios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(16), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ratios_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_financial_ratios_symbol_period", "symbol", "period"),
    )


class FinancialScoreModel(Base):
    """Persisted financial health scores."""

    __tablename__ = "financial_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(16), nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    recommendation: Mapped[str] = mapped_column(String(16), nullable=False)
    scores_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_financial_scores_symbol_created", "symbol", "created_at"),
    )


class FinancialAnalysisModel(Base):
    """Persisted full financial analysis reports."""

    __tablename__ = "financial_analysis"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(16), nullable=False)
    analysis_json: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ValuationHistoryModel(Base):
    """Persisted valuation history."""

    __tablename__ = "valuation_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_pe: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_pe: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_pb: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_valuation_history_symbol_period", "symbol", "period_end"),
    )


class FinancialAlertModel(Base):
    """Financial alert signals."""

    __tablename__ = "financial_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    trace_type: Mapped[str] = mapped_column(String(32), nullable=False)
    level: Mapped[str] = mapped_column(String(8), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    reasons_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    acknowledged: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_financial_alerts_symbol_type", "symbol", "trace_type"),
    )
