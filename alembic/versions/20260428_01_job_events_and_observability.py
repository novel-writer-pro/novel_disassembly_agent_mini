"""job events and observability fields

Revision ID: 20260428_01
Revises: 20260425_02
Create Date: 2026-04-28 16:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '20260428_01'
down_revision = '20260425_02'
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(name)


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(item["name"] == column for item in inspector.get_columns(table))


def upgrade() -> None:
    if _has_table('chapter_jobs'):
        for name, column in [
            ('current_stage', sa.Column('current_stage', sa.String(length=64), nullable=True)),
            ('progress_percent', sa.Column('progress_percent', sa.Integer(), nullable=False, server_default='0')),
            ('worker_id', sa.Column('worker_id', sa.String(length=128), nullable=True)),
            ('heartbeat_at', sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True)),
            ('next_retry_at', sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True)),
            ('failure_class', sa.Column('failure_class', sa.String(length=64), nullable=True)),
            ('failure_code', sa.Column('failure_code', sa.String(length=64), nullable=True)),
            ('provider_name', sa.Column('provider_name', sa.String(length=64), nullable=True)),
            ('model_name', sa.Column('model_name', sa.String(length=128), nullable=True)),
            ('queue_name', sa.Column('queue_name', sa.String(length=64), nullable=False, server_default='default')),
            ('trace_id', sa.Column('trace_id', sa.String(length=128), nullable=True)),
            ('control_run_id', sa.Column('control_run_id', sa.String(length=36), nullable=True)),
        ]:
            if not _has_column('chapter_jobs', name):
                op.add_column('chapter_jobs', column)

    if not _has_table('chapter_job_events'):
        op.create_table(
            'chapter_job_events',
            sa.Column('run_id', sa.String(length=36), nullable=False),
            sa.Column('branch_id', sa.String(length=36), nullable=False),
            sa.Column('chapter_index', sa.Integer(), nullable=False),
            sa.Column('job_id', sa.String(length=36), nullable=True),
            sa.Column('event_type', sa.String(length=64), nullable=False),
            sa.Column('stage', sa.String(length=64), nullable=True),
            sa.Column('level', sa.String(length=16), nullable=False, server_default='info'),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('payload_json', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['run_id'], ['analysis_runs.id']),
            sa.ForeignKeyConstraint(['branch_id'], ['run_branches.id']),
            sa.ForeignKeyConstraint(['job_id'], ['chapter_jobs.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_chapter_job_events_run_id'), 'chapter_job_events', ['run_id'])
        op.create_index(op.f('ix_chapter_job_events_branch_id'), 'chapter_job_events', ['branch_id'])
        op.create_index(op.f('ix_chapter_job_events_chapter_index'), 'chapter_job_events', ['chapter_index'])
        op.create_index(op.f('ix_chapter_job_events_job_id'), 'chapter_job_events', ['job_id'])


def downgrade() -> None:
    if _has_table('chapter_job_events'):
        op.drop_table('chapter_job_events')
