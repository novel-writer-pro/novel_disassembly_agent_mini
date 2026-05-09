"""Loom memory fields: add importance/conflict/version columns to fact_records,
graph_nodes, and graph_edges.

Revision ID: 20260509_01
Revises: 20260505_01
Create Date: 2026-05-09 20:00:00

These columns are all additive with server-side defaults, so existing rows
are safe and no data migration is required.  The columns back the Loom
layered-memory architecture (Phase 1):

  fact_records:
    importance_score  – episodic importance weight (0-1, default 0.5)
    decay_factor      – per-chapter decay multiplier (default 1.0)
    episodic_status   – active | decayed | superseded (default 'active')

  graph_nodes:
    conflict_status         – clean | contradiction | evolution | ambiguity | resolved
    loom_version            – monotonic version counter for evolution chains
    superseded_by_node_id   – FK-like pointer to the replacement node
    importance_score        – semantic importance weight (0-1, default 0.5)

  graph_edges:
    conflict_status  – clean | contradiction | evolution | ambiguity | resolved
    loom_version     – monotonic version counter
    is_active        – False when superseded by an evolution edge
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260509_01"
down_revision = "20260505_01"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    # ------------------------------------------------------------------
    # fact_records
    # ------------------------------------------------------------------
    if not _has_column("fact_records", "importance_score"):
        op.add_column(
            "fact_records",
            sa.Column("importance_score", sa.Float(), nullable=False, server_default="0.5"),
        )
    if not _has_column("fact_records", "decay_factor"):
        op.add_column(
            "fact_records",
            sa.Column("decay_factor", sa.Float(), nullable=False, server_default="1.0"),
        )
    if not _has_column("fact_records", "episodic_status"):
        op.add_column(
            "fact_records",
            sa.Column(
                "episodic_status",
                sa.String(length=32),
                nullable=False,
                server_default="active",
            ),
        )

    # ------------------------------------------------------------------
    # graph_nodes
    # ------------------------------------------------------------------
    if not _has_column("graph_nodes", "conflict_status"):
        op.add_column(
            "graph_nodes",
            sa.Column(
                "conflict_status",
                sa.String(length=32),
                nullable=False,
                server_default="clean",
            ),
        )
    if not _has_column("graph_nodes", "loom_version"):
        op.add_column(
            "graph_nodes",
            sa.Column("loom_version", sa.Integer(), nullable=False, server_default="1"),
        )
    if not _has_column("graph_nodes", "superseded_by_node_id"):
        op.add_column(
            "graph_nodes",
            sa.Column("superseded_by_node_id", sa.String(length=36), nullable=True),
        )
    if not _has_column("graph_nodes", "importance_score"):
        op.add_column(
            "graph_nodes",
            sa.Column("importance_score", sa.Float(), nullable=False, server_default="0.5"),
        )

    # ------------------------------------------------------------------
    # graph_edges
    # ------------------------------------------------------------------
    if not _has_column("graph_edges", "conflict_status"):
        op.add_column(
            "graph_edges",
            sa.Column(
                "conflict_status",
                sa.String(length=32),
                nullable=False,
                server_default="clean",
            ),
        )
    if not _has_column("graph_edges", "loom_version"):
        op.add_column(
            "graph_edges",
            sa.Column("loom_version", sa.Integer(), nullable=False, server_default="1"),
        )
    if not _has_column("graph_edges", "is_active"):
        op.add_column(
            "graph_edges",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        )


def downgrade() -> None:
    # graph_edges
    for col in ("is_active", "loom_version", "conflict_status"):
        if _has_column("graph_edges", col):
            op.drop_column("graph_edges", col)

    # graph_nodes
    for col in ("importance_score", "superseded_by_node_id", "loom_version", "conflict_status"):
        if _has_column("graph_nodes", col):
            op.drop_column("graph_nodes", col)

    # fact_records
    for col in ("episodic_status", "decay_factor", "importance_score"):
        if _has_column("fact_records", col):
            op.drop_column("fact_records", col)
