"""pipeline runs

Revision ID: 20260428_02
Revises: 20260428_01
Create Date: 2026-04-28 16:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '20260428_02'
down_revision = '20260428_01'
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(name)


def upgrade() -> None:
    if not _has_table('pipeline_runs'):
        op.create_table(
            'pipeline_runs',
            sa.Column('run_id', sa.String(length=36), nullable=False),
            sa.Column('branch_id', sa.String(length=36), nullable=False),
            sa.Column('mode', sa.String(length=32), nullable=False, server_default='range'),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
            sa.Column('target_from_chapter', sa.Integer(), nullable=True),
            sa.Column('target_to_chapter', sa.Integer(), nullable=True),
            sa.Column('concurrency', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('provider_profile', sa.String(length=128), nullable=True),
            sa.Column('created_by', sa.String(length=128), nullable=True),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('summary_json', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['run_id'], ['analysis_runs.id']),
            sa.ForeignKeyConstraint(['branch_id'], ['run_branches.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_pipeline_runs_run_id'), 'pipeline_runs', ['run_id'])
        op.create_index(op.f('ix_pipeline_runs_branch_id'), 'pipeline_runs', ['branch_id'])


def downgrade() -> None:
    if _has_table('pipeline_runs'):
        op.drop_table('pipeline_runs')
