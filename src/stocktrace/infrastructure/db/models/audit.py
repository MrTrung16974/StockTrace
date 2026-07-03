"""Audit event ORM model."""

from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from stocktrace.infrastructure.db.base import Base


class AuditEventModel(Base):
    """Append-only table for all domain events."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_trace_id", "trace_id"),
        Index("ix_audit_events_event_type", "event_type"),
        Index("ix_audit_events_aggregate_id", "aggregate_id"),
        Index("ix_audit_events_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
