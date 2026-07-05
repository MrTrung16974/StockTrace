"""Create financial analysis tables.

Revision ID: 0003_create_financial_tables
Revises: 0002_create_watchlist_items
Create Date: 2026-07-03 21:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_create_financial_tables"
down_revision = "0002_create_watchlist_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    op.create_table(
        "financial_statements",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("statement_type", sa.String(length=32), nullable=False),
        sa.Column("data_json", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="mock"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_financial_statements_symbol", "financial_statements", ["symbol"])
    op.create_index("ix_financial_statements_symbol_period", "financial_statements", ["symbol", "period"])

    op.create_table(
        "financial_ratios",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ratios_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_financial_ratios_symbol", "financial_ratios", ["symbol"])
    op.create_index("ix_financial_ratios_symbol_period", "financial_ratios", ["symbol", "period"])

    op.create_table(
        "financial_scores",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("recommendation", sa.String(length=16), nullable=False),
        sa.Column("scores_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_financial_scores_symbol", "financial_scores", ["symbol"])
    op.create_index("ix_financial_scores_symbol_created", "financial_scores", ["symbol", "created_at"])

    op.create_table(
        "financial_analysis",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("analysis_json", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_financial_analysis_symbol", "financial_analysis", ["symbol"])

    op.create_table(
        "valuation_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_pe", sa.Float(), nullable=True),
        sa.Column("average_pe", sa.Float(), nullable=True),
        sa.Column("current_pb", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("target_price", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_valuation_history_symbol", "valuation_history", ["symbol"])
    op.create_index("ix_valuation_history_symbol_period", "valuation_history", ["symbol", "period_end"])

    op.create_table(
        "financial_alerts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("trace_type", sa.String(length=32), nullable=False),
        sa.Column("level", sa.String(length=8), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("reasons_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_financial_alerts_symbol", "financial_alerts", ["symbol"])
    op.create_index("ix_financial_alerts_symbol_type", "financial_alerts", ["symbol", "trace_type"])


def downgrade() -> None:
    """Rollback migration."""
    op.drop_index("ix_financial_alerts_symbol_type", table_name="financial_alerts")
    op.drop_index("ix_financial_alerts_symbol", table_name="financial_alerts")
    op.drop_table("financial_alerts")

    op.drop_index("ix_valuation_history_symbol_period", table_name="valuation_history")
    op.drop_index("ix_valuation_history_symbol", table_name="valuation_history")
    op.drop_table("valuation_history")

    op.drop_index("ix_financial_analysis_symbol", table_name="financial_analysis")
    op.drop_table("financial_analysis")

    op.drop_index("ix_financial_scores_symbol_created", table_name="financial_scores")
    op.drop_index("ix_financial_scores_symbol", table_name="financial_scores")
    op.drop_table("financial_scores")

    op.drop_index("ix_financial_ratios_symbol_period", table_name="financial_ratios")
    op.drop_index("ix_financial_ratios_symbol", table_name="financial_ratios")
    op.drop_table("financial_ratios")

    op.drop_index("ix_financial_statements_symbol_period", table_name="financial_statements")
    op.drop_index("ix_financial_statements_symbol", table_name="financial_statements")
    op.drop_table("financial_statements")
