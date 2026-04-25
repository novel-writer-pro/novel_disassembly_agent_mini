"""prefer pg_jieba-backed retrieval config when available

Revision ID: 20260424_03
Revises: 20260424_02
Create Date: 2026-04-24 02:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '20260424_03'
down_revision = '20260424_02'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    op.execute('CREATE EXTENSION IF NOT EXISTS pg_jieba')
    has_table = sa.inspect(bind).has_table('retrieval_documents')
    if not has_table:
        return
    config_name = bind.execute(
        sa.text("SELECT cfgname FROM pg_ts_config WHERE cfgname = 'jiebacfg'")
    ).scalar_one_or_none()
    if config_name is None:
        return
    op.execute('DROP INDEX IF EXISTS ix_retrieval_documents_bm25_vector')
    op.execute('ALTER TABLE retrieval_documents DROP COLUMN IF EXISTS bm25_vector')
    op.execute(
        "ALTER TABLE retrieval_documents "
        "ADD COLUMN bm25_vector tsvector GENERATED ALWAYS AS "
        "(to_tsvector('jiebacfg', coalesce(bm25_text, ''))) STORED"
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_retrieval_documents_bm25_vector '
        'ON retrieval_documents USING GIN (bm25_vector)'
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return
    has_table = sa.inspect(bind).has_table('retrieval_documents')
    if not has_table:
        return
    op.execute('DROP INDEX IF EXISTS ix_retrieval_documents_bm25_vector')
    op.execute('ALTER TABLE retrieval_documents DROP COLUMN IF EXISTS bm25_vector')
    op.execute(
        "ALTER TABLE retrieval_documents "
        "ADD COLUMN bm25_vector tsvector GENERATED ALWAYS AS "
        "(to_tsvector('simple', coalesce(bm25_text, ''))) STORED"
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_retrieval_documents_bm25_vector '
        'ON retrieval_documents USING GIN (bm25_vector)'
    )
