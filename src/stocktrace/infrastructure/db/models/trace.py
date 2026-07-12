"""Trace engine ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from stocktrace.infrastructure.db.base import Base


class TraceSourceModel(Base):
    """Persisted trace source metadata."""

    __tablename__ = "trace_sources"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    rank: Mapped[int] = mapped_column(nullable=False)
    official: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
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
        CheckConstraint("rank >= 1", name="ck_trace_sources_rank_positive"),
        Index("ix_trace_sources_type_rank", "source_type", "rank"),
    )


class TraceDocumentModel(Base):
    """Persisted source document used for trace provenance."""

    __tablename__ = "trace_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("trace_sources.code"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_trace_documents_source_published", "source_code", "published_at"),
        Index("ix_trace_documents_checksum", "checksum"),
    )


class TraceEventModel(Base):
    """Persisted normalized trace event."""

    __tablename__ = "trace_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    symbol: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("trace_sources.code"),
        nullable=False,
        index=True,
    )
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("trace_documents.id"),
        nullable=True,
        index=True,
    )
    reasons_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_trace_events_confidence_range",
        ),
        Index("ix_trace_events_symbol_type_created", "symbol", "event_type", "created_at"),
        Index("ix_trace_events_type_created", "event_type", "created_at"),
        Index("ix_trace_events_source_created", "source_code", "created_at"),
    )
