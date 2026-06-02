"""Create watchlist items.

Revision ID: 0002_create_watchlist_items
Revises: 0001_initial_schema
Create Date: 2026-06-02 20:20:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_create_watchlist_items"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "symbol", name="uq_watchlist_items_owner_symbol"),
    )
    op.create_index("ix_watchlist_items_owner_id", "watchlist_items", ["owner_id"])
    op.create_index("ix_watchlist_items_symbol", "watchlist_items", ["symbol"])


def downgrade() -> None:
    """Rollback migration."""
    op.drop_index("ix_watchlist_items_symbol", table_name="watchlist_items")
    op.drop_index("ix_watchlist_items_owner_id", table_name="watchlist_items")
    op.drop_table("watchlist_items")
