"""add owner_user_id to library tables

Revision ID: 20260513_01
Revises: 20260511_02
Create Date: 2026-05-13 23:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260513_01"
down_revision = "20260511_02"
branch_labels = None
depends_on = None

TABLES = ("novel_sources", "analysis_runs", "run_branches")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in TABLES:
        if not inspector.has_table(table):
            continue
        columns = {col["name"] for col in inspector.get_columns(table)}
        if "owner_user_id" not in columns:
            op.add_column(
                table,
                sa.Column(
                    "owner_user_id",
                    sa.String(64),
                    nullable=False,
                    server_default="local-default",
                ),
            )
            op.create_index(
                f"ix_{table}_owner_user_id",
                table,
                ["owner_user_id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in TABLES:
        if not inspector.has_table(table):
            continue
        existing_indexes = {idx["name"] for idx in inspector.get_indexes(table)}
        if f"ix_{table}_owner_user_id" in existing_indexes:
            op.drop_index(f"ix_{table}_owner_user_id", table_name=table)
        columns = {col["name"] for col in inspector.get_columns(table)}
        if "owner_user_id" in columns:
            op.drop_column(table, "owner_user_id")
