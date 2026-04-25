"""initial schema

Revision ID: 20260424_01
Revises:
Create Date: 2026-04-24 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '20260424_01'
down_revision = None
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(name)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute('CREATE EXTENSION IF NOT EXISTS vector')
        op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
        op.execute('CREATE EXTENSION IF NOT EXISTS pg_textsearch')

    if not _has_table('novel_sources'):
        op.create_table(
            'novel_sources',
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('source_path', sa.Text(), nullable=False),
            sa.Column('source_hash', sa.String(length=64), nullable=False),
            sa.Column('metadata_json', sa.JSON(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_novel_sources_source_hash'), 'novel_sources', ['source_hash'])

    if not _has_table('chapter_manifests'):
        op.create_table(
            'chapter_manifests',
            sa.Column('novel_id', sa.String(length=36), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False),
            sa.Column('splitter_version', sa.String(length=64), nullable=False),
            sa.Column('chapter_count', sa.Integer(), nullable=False),
            sa.Column('notes', sa.JSON(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['novel_id'], ['novel_sources.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('novel_id', 'version', name='uq_manifest_version'),
        )
        op.create_index(op.f('ix_chapter_manifests_novel_id'), 'chapter_manifests', ['novel_id'])

    if not _has_table('chapter_segments'):
        op.create_table(
            'chapter_segments',
            sa.Column('manifest_id', sa.String(length=36), nullable=False),
            sa.Column('chapter_index', sa.Integer(), nullable=False),
            sa.Column('raw_heading', sa.Text(), nullable=False),
            sa.Column('normalized_chapter_no', sa.Integer(), nullable=True),
            sa.Column('normalized_title', sa.Text(), nullable=False),
            sa.Column('start_offset', sa.Integer(), nullable=False),
            sa.Column('end_offset', sa.Integer(), nullable=False),
            sa.Column('content_hash', sa.String(length=64), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['manifest_id'], ['chapter_manifests.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('manifest_id', 'chapter_index', name='uq_manifest_chapter'),
        )
        op.create_index(op.f('ix_chapter_segments_manifest_id'), 'chapter_segments', ['manifest_id'])

    if not _has_table('analysis_runs'):
        op.create_table(
            'analysis_runs',
            sa.Column('novel_id', sa.String(length=36), nullable=False),
            sa.Column('manifest_id', sa.String(length=36), nullable=False),
            sa.Column('llm_base_url', sa.Text(), nullable=False),
            sa.Column('llm_model_name', sa.String(length=128), nullable=False),
            sa.Column('analysis_profile', sa.JSON(), nullable=False),
            sa.Column('active_branch_id', sa.String(length=36), nullable=True),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['manifest_id'], ['chapter_manifests.id']),
            sa.ForeignKeyConstraint(['novel_id'], ['novel_sources.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_analysis_runs_manifest_id'), 'analysis_runs', ['manifest_id'])
        op.create_index(op.f('ix_analysis_runs_novel_id'), 'analysis_runs', ['novel_id'])

    if not _has_table('run_branches'):
        op.create_table(
            'run_branches',
            sa.Column('run_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('parent_branch_id', sa.String(length=36), nullable=True),
            sa.Column('fork_after_chapter_index', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['parent_branch_id'], ['run_branches.id']),
            sa.ForeignKeyConstraint(['run_id'], ['analysis_runs.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_run_branches_run_id'), 'run_branches', ['run_id'])

    if not _has_table('run_checkpoints'):
        op.create_table(
            'run_checkpoints',
            sa.Column('branch_id', sa.String(length=36), nullable=False),
            sa.Column('chapter_index', sa.Integer(), nullable=False),
            sa.Column('langgraph_thread_id', sa.String(length=255), nullable=True),
            sa.Column('langgraph_checkpoint_id', sa.String(length=255), nullable=True),
            sa.Column('state_summary', sa.JSON(), nullable=False),
            sa.Column('inherited_from_branch_id', sa.String(length=36), nullable=True),
            sa.Column('is_inherited', sa.Boolean(), nullable=False),
            sa.Column('visibility', sa.String(length=32), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['branch_id'], ['run_branches.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('branch_id', 'chapter_index', name='uq_branch_checkpoint'),
        )
        op.create_index(op.f('ix_run_checkpoints_branch_id'), 'run_checkpoints', ['branch_id'])

    if not _has_table('chapter_artifacts'):
        op.create_table(
            'chapter_artifacts',
            sa.Column('branch_id', sa.String(length=36), nullable=False),
            sa.Column('chapter_index', sa.Integer(), nullable=False),
            sa.Column('artifact_type', sa.String(length=64), nullable=False),
            sa.Column('payload_json', sa.JSON(), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False),
            sa.Column('visibility', sa.String(length=32), nullable=False),
            sa.Column('source_kind', sa.String(length=32), nullable=False),
            sa.Column('participates_in_downstream', sa.Boolean(), nullable=False),
            sa.Column('inherited_from_branch_id', sa.String(length=36), nullable=True),
            sa.Column('is_inherited', sa.Boolean(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['branch_id'], ['run_branches.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_chapter_artifacts_branch_id'), 'chapter_artifacts', ['branch_id'])

    if not _has_table('chapter_jobs'):
        op.create_table(
            'chapter_jobs',
            sa.Column('branch_id', sa.String(length=36), nullable=False),
            sa.Column('chapter_index', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False),
            sa.Column('attempts', sa.Integer(), nullable=False),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['branch_id'], ['run_branches.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('branch_id', 'chapter_index', name='uq_branch_job'),
        )
        op.create_index(op.f('ix_chapter_jobs_branch_id'), 'chapter_jobs', ['branch_id'])

    if not _has_table('chapter_raw_outputs'):
        op.create_table(
            'chapter_raw_outputs',
            sa.Column('run_id', sa.String(length=36), nullable=False),
            sa.Column('branch_id', sa.String(length=36), nullable=False),
            sa.Column('chapter_index', sa.Integer(), nullable=False),
            sa.Column('job_attempt', sa.Integer(), nullable=False),
            sa.Column('prompt_version', sa.String(length=64), nullable=False),
            sa.Column('schema_version', sa.String(length=64), nullable=False),
            sa.Column('raw_response_text', sa.Text(), nullable=False),
            sa.Column('parsed_json', sa.JSON(), nullable=True),
            sa.Column('parse_status', sa.String(length=32), nullable=False),
            sa.Column('parse_error', sa.Text(), nullable=True),
            sa.Column('invocation_metadata', sa.JSON(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['branch_id'], ['run_branches.id']),
            sa.ForeignKeyConstraint(['run_id'], ['analysis_runs.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_chapter_raw_outputs_branch_id'), 'chapter_raw_outputs', ['branch_id'])
        op.create_index(op.f('ix_chapter_raw_outputs_run_id'), 'chapter_raw_outputs', ['run_id'])


def downgrade() -> None:
    for table in [
        'chapter_raw_outputs',
        'chapter_jobs',
        'chapter_artifacts',
        'run_checkpoints',
        'run_branches',
        'analysis_runs',
        'chapter_segments',
        'chapter_manifests',
        'novel_sources',
    ]:
        if _has_table(table):
            op.drop_table(table)
