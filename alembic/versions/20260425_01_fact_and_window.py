"""fact records and window artifacts

Revision ID: 20260425_01
Revises: 20260424_03
Create Date: 2026-04-25 00:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '20260425_01'
down_revision = '20260424_03'
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(name)


def upgrade() -> None:
    if not _has_table('fact_records'):
        op.create_table(
            'fact_records',
            sa.Column('branch_id', sa.String(length=36), nullable=False),
            sa.Column('chapter_index', sa.Integer(), nullable=False),
            sa.Column('fact_type', sa.String(length=64), nullable=False),
            sa.Column('label', sa.Text(), nullable=False),
            sa.Column('evidence_list', sa.JSON(), nullable=False),
            sa.Column('confidence', sa.Float(), nullable=False),
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
        )
        op.create_index(op.f('ix_fact_records_branch_id'), 'fact_records', ['branch_id'])

    if not _has_table('window_artifacts'):
        op.create_table(
            'window_artifacts',
            sa.Column('branch_id', sa.String(length=36), nullable=False),
            sa.Column('window_start_chapter', sa.Integer(), nullable=False),
            sa.Column('window_end_chapter', sa.Integer(), nullable=False),
            sa.Column('window_type', sa.String(length=32), nullable=False),
            sa.Column('payload_json', sa.JSON(), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False),
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
            sa.UniqueConstraint(
                'branch_id',
                'window_start_chapter',
                'window_end_chapter',
                name='uq_window_artifact_range',
            ),
        )
        op.create_index(op.f('ix_window_artifacts_branch_id'), 'window_artifacts', ['branch_id'])


def downgrade() -> None:
    for table in ['window_artifacts', 'fact_records']:
        if _has_table(table):
            op.drop_table(table)
