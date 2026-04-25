"""graph nodes and edges

Revision ID: 20260425_02
Revises: 20260425_01
Create Date: 2026-04-25 01:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '20260425_02'
down_revision = '20260425_01'
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(name)


def upgrade() -> None:
    if not _has_table('graph_nodes'):
        op.create_table(
            'graph_nodes',
            sa.Column('branch_id', sa.String(length=36), nullable=False),
            sa.Column('node_type', sa.String(length=64), nullable=False),
            sa.Column('label', sa.Text(), nullable=False),
            sa.Column('chapter_first_seen', sa.Integer(), nullable=False),
            sa.Column('chapter_last_seen', sa.Integer(), nullable=False),
            sa.Column('occurrence_count', sa.Integer(), nullable=False),
            sa.Column('metadata_json', sa.JSON(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column(
                'created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
            ),
            sa.Column(
                'updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
            ),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['branch_id'], ['run_branches.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('branch_id', 'node_type', 'label', name='uq_graph_node_identity'),
        )
        op.create_index(op.f('ix_graph_nodes_branch_id'), 'graph_nodes', ['branch_id'])

    if not _has_table('graph_edges'):
        op.create_table(
            'graph_edges',
            sa.Column('branch_id', sa.String(length=36), nullable=False),
            sa.Column('source_node_id', sa.String(length=36), nullable=False),
            sa.Column('target_node_id', sa.String(length=36), nullable=False),
            sa.Column('edge_type', sa.String(length=64), nullable=False),
            sa.Column('weight', sa.Float(), nullable=False),
            sa.Column('chapter_first_seen', sa.Integer(), nullable=False),
            sa.Column('chapter_last_seen', sa.Integer(), nullable=False),
            sa.Column('metadata_json', sa.JSON(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column(
                'created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
            ),
            sa.Column(
                'updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
            ),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['branch_id'], ['run_branches.id']),
            sa.ForeignKeyConstraint(['source_node_id'], ['graph_nodes.id']),
            sa.ForeignKeyConstraint(['target_node_id'], ['graph_nodes.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint(
                'branch_id',
                'source_node_id',
                'target_node_id',
                'edge_type',
                name='uq_graph_edge_identity',
            ),
        )
        op.create_index(op.f('ix_graph_edges_branch_id'), 'graph_edges', ['branch_id'])


def downgrade() -> None:
    for table in ['graph_edges', 'graph_nodes']:
        if _has_table(table):
            op.drop_table(table)
