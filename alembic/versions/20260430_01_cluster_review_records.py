"""cluster review records

Revision ID: 20260430_01
Revises: 20260428_02
Create Date: 2026-04-30 08:45:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '20260430_01'
down_revision = '20260428_02'
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
    if not _has_table('cluster_review_records'):
        op.create_table(
            'cluster_review_records',
            sa.Column('branch_id', sa.String(length=36), nullable=False),
            sa.Column('cluster_key', sa.String(length=255), nullable=False),
            sa.Column('cluster_status', sa.String(length=32), nullable=False, server_default='open'),
            sa.Column('review_result', sa.String(length=64), nullable=False, server_default=''),
            sa.Column('review_notes', sa.Text(), nullable=False, server_default=''),
            sa.Column('review_owner', sa.String(length=255), nullable=False, server_default=''),
            sa.Column('resolved_at_text', sa.String(length=64), nullable=False, server_default=''),
            sa.Column('visibility', sa.String(length=32), nullable=False, server_default='active'),
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['branch_id'], ['run_branches.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('branch_id', 'cluster_key', name='uq_cluster_review_branch_key'),
        )
        op.create_index('ix_cluster_review_records_branch_id', 'cluster_review_records', ['branch_id'])
        op.create_index('ix_cluster_review_records_cluster_key', 'cluster_review_records', ['cluster_key'])

    if not _has_table('cluster_review_event_records'):
        op.create_table(
            'cluster_review_event_records',
            sa.Column('branch_id', sa.String(length=36), nullable=False),
            sa.Column('cluster_key', sa.String(length=255), nullable=False),
            sa.Column('previous_cluster_status', sa.String(length=32), nullable=False, server_default=''),
            sa.Column('previous_review_result', sa.String(length=64), nullable=False, server_default=''),
            sa.Column('previous_review_notes', sa.Text(), nullable=False, server_default=''),
            sa.Column('previous_review_owner', sa.String(length=255), nullable=False, server_default=''),
            sa.Column('previous_resolved_at_text', sa.String(length=64), nullable=False, server_default=''),
            sa.Column('cluster_status', sa.String(length=32), nullable=False, server_default='open'),
            sa.Column('review_result', sa.String(length=64), nullable=False, server_default=''),
            sa.Column('review_notes', sa.Text(), nullable=False, server_default=''),
            sa.Column('review_owner', sa.String(length=255), nullable=False, server_default=''),
            sa.Column('resolved_at_text', sa.String(length=64), nullable=False, server_default=''),
            sa.Column('event_type', sa.String(length=64), nullable=False, server_default='status_update'),
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['branch_id'], ['run_branches.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_cluster_review_event_records_branch_id', 'cluster_review_event_records', ['branch_id'])
        op.create_index('ix_cluster_review_event_records_cluster_key', 'cluster_review_event_records', ['cluster_key'])
    else:
        for column_name, column_type in [
            ('previous_review_notes', sa.Text()),
            ('previous_review_owner', sa.String(length=255)),
            ('previous_resolved_at_text', sa.String(length=64)),
        ]:
            if not _has_column('cluster_review_event_records', column_name):
                op.add_column(
                    'cluster_review_event_records',
                    sa.Column(column_name, column_type, nullable=False, server_default=''),
                )


def downgrade() -> None:
    if _has_table('cluster_review_event_records'):
        op.drop_table('cluster_review_event_records')
    if _has_table('cluster_review_records'):
        op.drop_table('cluster_review_records')
