"""reader feedback comments table

Revision ID: 20260505_01
Revises: 20260504_01
Create Date: 2026-05-05 18:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260505_01"
down_revision = "20260504_01"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(name)


def upgrade() -> None:
    if not _has_table("reader_feedback_comments"):
        op.create_table(
            "reader_feedback_comments",
            sa.Column("branch_id", sa.String(length=36), nullable=False),
            sa.Column("chapter_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("source", sa.String(length=64), nullable=False, server_default="manual"),
            sa.Column("comment_text", sa.Text(), nullable=False),
            sa.Column("sentiment", sa.String(length=32), nullable=False, server_default="mixed"),
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["branch_id"], ["run_branches.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_reader_feedback_comments_branch_id"), "reader_feedback_comments", ["branch_id"])
        op.create_index(op.f("ix_reader_feedback_comments_chapter_index"), "reader_feedback_comments", ["chapter_index"])


def downgrade() -> None:
    if _has_table("reader_feedback_comments"):
        op.drop_index(op.f("ix_reader_feedback_comments_chapter_index"), table_name="reader_feedback_comments")
        op.drop_index(op.f("ix_reader_feedback_comments_branch_id"), table_name="reader_feedback_comments")
        op.drop_table("reader_feedback_comments")
