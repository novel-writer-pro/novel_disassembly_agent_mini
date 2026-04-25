"""retrieval materialization tables

Revision ID: 20260424_02
Revises: 20260424_01
Create Date: 2026-04-24 00:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '20260424_02'
down_revision = '20260424_01'
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(name)


def _tsvector_ddl() -> str:
    return (
        "ALTER TABLE retrieval_documents "
        "ADD COLUMN IF NOT EXISTS bm25_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(bm25_text, ''))) STORED"
    )


def upgrade() -> None:
    if not _has_table('retrieval_documents'):
        op.create_table(
            'retrieval_documents',
            sa.Column('branch_id', sa.String(length=36), nullable=False),
            sa.Column('chapter_index', sa.Integer(), nullable=False),
            sa.Column('title', sa.Text(), nullable=False),
            sa.Column('summary_text', sa.Text(), nullable=False),
            sa.Column('bm25_text', sa.Text(), nullable=False),
            sa.Column('keyword_list', sa.JSON(), nullable=False),
            sa.Column('query_hints', sa.JSON(), nullable=False),
            sa.Column('materialization_status', sa.String(length=32), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column(
                'created_at',
                sa.DateTime(timezone=True),
                server_default=sa.text('CURRENT_TIMESTAMP'),
                nullable=False,
            ),
            sa.Column(
                'updated_at',
                sa.DateTime(timezone=True),
                server_default=sa.text('CURRENT_TIMESTAMP'),
                nullable=False,
            ),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['branch_id'], ['run_branches.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('branch_id', 'chapter_index', name='uq_retrieval_document'),
        )
        op.create_index(
            op.f('ix_retrieval_documents_branch_id'),
            'retrieval_documents',
            ['branch_id'],
        )
        if op.get_bind().dialect.name == 'postgresql':
            op.execute(_tsvector_ddl())
            op.execute(
                "CREATE INDEX IF NOT EXISTS ix_retrieval_documents_bm25_vector ON retrieval_documents USING GIN (bm25_vector)"
            )

    if not _has_table('retrieval_chunks'):
        op.create_table(
            'retrieval_chunks',
            sa.Column('document_id', sa.String(length=36), nullable=False),
            sa.Column('chunk_order', sa.Integer(), nullable=False),
            sa.Column('text', sa.Text(), nullable=False),
            sa.Column('start_offset', sa.Integer(), nullable=False),
            sa.Column('end_offset', sa.Integer(), nullable=False),
            sa.Column('embedding_status', sa.String(length=32), nullable=False),
            sa.Column('keyword_list', sa.JSON(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column(
                'created_at',
                sa.DateTime(timezone=True),
                server_default=sa.text('CURRENT_TIMESTAMP'),
                nullable=False,
            ),
            sa.Column(
                'updated_at',
                sa.DateTime(timezone=True),
                server_default=sa.text('CURRENT_TIMESTAMP'),
                nullable=False,
            ),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['document_id'], ['retrieval_documents.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('document_id', 'chunk_order', name='uq_document_chunk_order'),
        )
        op.create_index(
            op.f('ix_retrieval_chunks_document_id'),
            'retrieval_chunks',
            ['document_id'],
        )

    if not _has_table('chunk_embeddings'):
        op.create_table(
            'chunk_embeddings',
            sa.Column('chunk_id', sa.String(length=36), nullable=False),
            sa.Column('model_name', sa.String(length=128), nullable=False),
            sa.Column('vector_dim', sa.Integer(), nullable=False),
            sa.Column('vector_payload', sa.JSON(), nullable=False),
            sa.Column('l2_norm', sa.Float(), nullable=True),
            sa.Column('status', sa.String(length=32), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column(
                'created_at',
                sa.DateTime(timezone=True),
                server_default=sa.text('CURRENT_TIMESTAMP'),
                nullable=False,
            ),
            sa.Column(
                'updated_at',
                sa.DateTime(timezone=True),
                server_default=sa.text('CURRENT_TIMESTAMP'),
                nullable=False,
            ),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['chunk_id'], ['retrieval_chunks.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('chunk_id', name='uq_chunk_embedding_chunk'),
        )
        op.create_index(
            op.f('ix_chunk_embeddings_chunk_id'),
            'chunk_embeddings',
            ['chunk_id'],
        )


def downgrade() -> None:
    for table in ['chunk_embeddings', 'retrieval_chunks', 'retrieval_documents']:
        if _has_table(table):
            op.drop_table(table)
