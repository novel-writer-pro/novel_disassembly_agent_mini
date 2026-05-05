"""cluster review records compatibility bridge.

Revision ID: 20260430_02
Revises: 20260430_01
Create Date: 2026-04-30 08:45:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '20260430_02'
down_revision = '20260430_01'
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(name)


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return False
    return any(column['name'] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    """Historical follow-up migration kept as a no-op compatibility bridge.

    The real table creation/column backfill path is already handled by
    20260429_01 and 20260430_01_cluster_review_tables.py. This revision exists
    only to preserve a linear Alembic history for empty databases and to avoid
    duplicate-head failures.
    """
    _ = op


def downgrade() -> None:
    _ = op
