"""add risk audit record tables for gate checker results and chapter risk cards

Revision ID: 20260511_02
Revises: 20260509_01
Create Date: 2026-05-11 09:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260511_02"
down_revision = "20260509_01"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(name)


def upgrade() -> None:
    if not _has_table("gate_checker_results"):
        op.create_table(
            "gate_checker_results",
            sa.Column("branch_id", sa.String(length=36), nullable=False),
            sa.Column("chapter_index", sa.Integer(), nullable=False),
            sa.Column("checker_name", sa.String(length=64), nullable=False),
            sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="ready"),
            sa.Column("visibility", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["branch_id"], ["run_branches.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_gate_checker_results_branch_id"), "gate_checker_results", ["branch_id"])
        op.create_index(op.f("ix_gate_checker_results_chapter_index"), "gate_checker_results", ["chapter_index"])
        op.create_index(op.f("ix_gate_checker_results_checker_name"), "gate_checker_results", ["checker_name"])

    if not _has_table("chapter_risk_cards"):
        op.create_table(
            "chapter_risk_cards",
            sa.Column("branch_id", sa.String(length=36), nullable=False),
            sa.Column("chapter_index", sa.Integer(), nullable=False),
            sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="ready"),
            sa.Column("visibility", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["branch_id"], ["run_branches.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_chapter_risk_cards_branch_id"), "chapter_risk_cards", ["branch_id"])
        op.create_index(op.f("ix_chapter_risk_cards_chapter_index"), "chapter_risk_cards", ["chapter_index"])


def downgrade() -> None:
    if _has_table("chapter_risk_cards"):
        op.drop_table("chapter_risk_cards")
    if _has_table("gate_checker_results"):
        op.drop_table("gate_checker_results")
