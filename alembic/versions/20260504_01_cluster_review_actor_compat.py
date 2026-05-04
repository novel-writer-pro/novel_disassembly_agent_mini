"""cluster review actor compatibility columns

Revision ID: 20260504_01
Revises: 20260502_01
Create Date: 2026-05-04 10:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260504_01"
down_revision = "20260502_01"
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
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if _has_table("cluster_review_records") and not _has_column(
        "cluster_review_records", "review_actor"
    ):
        op.add_column(
            "cluster_review_records",
            sa.Column("review_actor", sa.String(length=255), nullable=False, server_default=""),
        )
        op.execute(
            sa.text(
                """
                UPDATE cluster_review_records
                SET review_actor = review_owner
                WHERE review_actor = ''
                """
            )
        )

    if _has_table("cluster_review_event_records"):
        for name, column in [
            (
                "previous_cluster_status",
                sa.Column(
                    "previous_cluster_status",
                    sa.String(length=32),
                    nullable=False,
                    server_default="",
                ),
            ),
            (
                "previous_review_result",
                sa.Column(
                    "previous_review_result",
                    sa.String(length=64),
                    nullable=False,
                    server_default="",
                ),
            ),
            (
                "previous_review_actor",
                sa.Column(
                    "previous_review_actor",
                    sa.String(length=255),
                    nullable=False,
                    server_default="",
                ),
            ),
            (
                "review_actor",
                sa.Column("review_actor", sa.String(length=255), nullable=False, server_default=""),
            ),
        ]:
            if not _has_column("cluster_review_event_records", name):
                op.add_column("cluster_review_event_records", column)

        if _has_column("cluster_review_event_records", "review_actor"):
            op.execute(
                sa.text(
                    """
                    UPDATE cluster_review_event_records
                    SET review_actor = review_owner
                    WHERE review_actor = ''
                    """
                )
            )
        if _has_column("cluster_review_event_records", "previous_review_actor"):
            op.execute(
                sa.text(
                    """
                    UPDATE cluster_review_event_records
                    SET previous_review_actor = previous_review_owner
                    WHERE previous_review_actor = ''
                    """
                )
            )


def downgrade() -> None:
    # Compatibility columns are intentionally not removed in downgrade, to avoid
    # discarding review metadata from partially upgraded environments.
    _ = op
