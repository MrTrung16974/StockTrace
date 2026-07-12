"""Create trace engine tables.

Revision ID: 0004_create_trace_engine_tables
Revises: 0003_create_financial_tables
Create Date: 2026-07-11 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_create_trace_engine_tables"
down_revision = "0003_create_financial_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    op.create_table(
        "trace_sources",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("official", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("rank >= 1", name="ck_trace_sources_rank_positive"),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_index("ix_trace_sources_type_rank", "trace_sources", ["source_type", "rank"])

    op.create_table(
        "trace_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_code", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_code"], ["trace_sources.code"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trace_documents_source_code", "trace_documents", ["source_code"])
    op.create_index(
        "ix_trace_documents_source_published",
        "trace_documents",
        ["source_code", "published_at"],
    )
    op.create_index("ix_trace_documents_checksum", "trace_documents", ["checksum"])

    op.create_table(
        "trace_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=True),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_code", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=True),
        sa.Column("reasons_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_trace_events_confidence_range",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["trace_documents.id"]),
        sa.ForeignKeyConstraint(["source_code"], ["trace_sources.code"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trace_events_symbol", "trace_events", ["symbol"])
    op.create_index("ix_trace_events_source_code", "trace_events", ["source_code"])
    op.create_index("ix_trace_events_document_id", "trace_events", ["document_id"])
    op.create_index(
        "ix_trace_events_symbol_type_created",
        "trace_events",
        ["symbol", "event_type", "created_at"],
    )
    op.create_index("ix_trace_events_type_created", "trace_events", ["event_type", "created_at"])
    op.create_index("ix_trace_events_source_created", "trace_events", ["source_code", "created_at"])


def downgrade() -> None:
    """Rollback migration."""
    op.drop_index("ix_trace_events_source_created", table_name="trace_events")
    op.drop_index("ix_trace_events_type_created", table_name="trace_events")
    op.drop_index("ix_trace_events_symbol_type_created", table_name="trace_events")
    op.drop_index("ix_trace_events_document_id", table_name="trace_events")
    op.drop_index("ix_trace_events_source_code", table_name="trace_events")
    op.drop_index("ix_trace_events_symbol", table_name="trace_events")
    op.drop_table("trace_events")

    op.drop_index("ix_trace_documents_checksum", table_name="trace_documents")
    op.drop_index("ix_trace_documents_source_published", table_name="trace_documents")
    op.drop_index("ix_trace_documents_source_code", table_name="trace_documents")
    op.drop_table("trace_documents")

    op.drop_index("ix_trace_sources_type_rank", table_name="trace_sources")
    op.drop_table("trace_sources")
