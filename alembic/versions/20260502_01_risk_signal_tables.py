"""risk signal semantic tables

Revision ID: 20260502_01
Revises: 20260430_02
Create Date: 2026-05-02 10:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260502_01"
down_revision = "20260430_02"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(name)


def upgrade() -> None:
    if not _has_table("risk_semantic_signals"):
        op.create_table(
            "risk_semantic_signals",
            sa.Column("branch_id", sa.String(length=36), nullable=False),
            sa.Column("chapter_index", sa.Integer(), nullable=False),
            sa.Column("signal_type", sa.String(length=64), nullable=False),
            sa.Column("source_field", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("raw_text", sa.Text(), nullable=False),
            sa.Column("canonical_label", sa.Text(), nullable=False, server_default=""),
            sa.Column("canonical_group", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("vector_payload", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
            sa.Column("vector_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("vector_dim", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="ready"),
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
        op.create_index(
            op.f("ix_risk_semantic_signals_branch_id"),
            "risk_semantic_signals",
            ["branch_id"],
        )
        op.create_index(
            op.f("ix_risk_semantic_signals_chapter_index"),
            "risk_semantic_signals",
            ["chapter_index"],
        )
        op.create_index(
            op.f("ix_risk_semantic_signals_signal_type"),
            "risk_semantic_signals",
            ["signal_type"],
        )

    if not _has_table("risk_signal_links"):
        op.create_table(
            "risk_signal_links",
            sa.Column("branch_id", sa.String(length=36), nullable=False),
            sa.Column("chapter_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("from_signal_id", sa.String(length=36), nullable=False),
            sa.Column("to_signal_id", sa.String(length=36), nullable=False),
            sa.Column("link_type", sa.String(length=64), nullable=False),
            sa.Column("score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("evidence_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
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
            sa.ForeignKeyConstraint(["from_signal_id"], ["risk_semantic_signals.id"]),
            sa.ForeignKeyConstraint(["to_signal_id"], ["risk_semantic_signals.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_risk_signal_links_branch_id"), "risk_signal_links", ["branch_id"])
        op.create_index(
            op.f("ix_risk_signal_links_chapter_index"),
            "risk_signal_links",
            ["chapter_index"],
        )
        op.create_index(
            op.f("ix_risk_signal_links_from_signal_id"),
            "risk_signal_links",
            ["from_signal_id"],
        )
        op.create_index(
            op.f("ix_risk_signal_links_to_signal_id"),
            "risk_signal_links",
            ["to_signal_id"],
        )
        op.create_index(op.f("ix_risk_signal_links_link_type"), "risk_signal_links", ["link_type"])

    if not _has_table("risk_signal_clusters"):
        op.create_table(
            "risk_signal_clusters",
            sa.Column("branch_id", sa.String(length=36), nullable=False),
            sa.Column("cluster_key", sa.String(length=255), nullable=False),
            sa.Column("signal_type", sa.String(length=64), nullable=False),
            sa.Column("summary_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("signal_ids_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
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
        op.create_index(
            op.f("ix_risk_signal_clusters_branch_id"),
            "risk_signal_clusters",
            ["branch_id"],
        )
        op.create_index(
            op.f("ix_risk_signal_clusters_cluster_key"),
            "risk_signal_clusters",
            ["cluster_key"],
        )
        op.create_index(
            op.f("ix_risk_signal_clusters_signal_type"),
            "risk_signal_clusters",
            ["signal_type"],
        )


def downgrade() -> None:
    if _has_table("risk_signal_clusters"):
        op.drop_table("risk_signal_clusters")
    if _has_table("risk_signal_links"):
        op.drop_table("risk_signal_links")
    if _has_table("risk_semantic_signals"):
        op.drop_table("risk_semantic_signals")
