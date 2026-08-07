"""Create portfolio items.

Revision ID: 0005_create_portfolio_items
Revises: 0004_create_trace_engine_tables
Create Date: 2026-08-07 17:15:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_create_portfolio_items"
down_revision = "0004_create_trace_engine_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    op.create_table(
        "portfolio_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("average_price", sa.Numeric(precision=18, scale=4), nullable=False, server_default="0"),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "symbol", name="uq_portfolio_items_owner_symbol"),
    )
    op.create_index("ix_portfolio_items_owner_id", "portfolio_items", ["owner_id"])
    op.create_index("ix_portfolio_items_symbol", "portfolio_items", ["symbol"])


def downgrade() -> None:
    """Rollback migration."""
    op.drop_index("ix_portfolio_items_symbol", table_name="portfolio_items")
    op.drop_index("ix_portfolio_items_owner_id", table_name="portfolio_items")
    op.drop_table("portfolio_items")
