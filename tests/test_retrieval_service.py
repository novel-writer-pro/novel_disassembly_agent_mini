from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings
from novel_analyzer.database.models import ChunkEmbedding, RetrievalChunk, RetrievalDocument
from novel_analyzer.database.session import create_schema
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.retrieval_service import RetrievalService
from novel_analyzer.services.run_service import RunService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def _artifact_payload() -> dict[str, object]:
    return {
        'chapter_index': 1,
        'normalized_title': '命格初现',
        'chapter_summary': '卫图觉醒命格',
        'key_entities': ['卫图'],
        'key_events': ['觉醒命格'],
        'continuity_notes': ['开启求仙主线'],
        'dimensions': [],
        'writer_learning_notes': [],
        'unsupported_inferences': [],
        'ambiguous_points': [],
        'needs_human_review': False,
    }


def test_retrieval_materialization_creates_document_chunk_and_embedding(tmp_path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        artifact = RunService(session).record_chapter_artifact(branch.id, 1, _artifact_payload())
        document = RetrievalService(session, Settings()).materialize_for_artifact(artifact.id)
        loaded_document = session.scalar(
            select(RetrievalDocument).where(RetrievalDocument.id == document.id)
        )
        assert loaded_document is not None
        assert loaded_document.keyword_list == ['卫图', '觉醒命格']
        chunk = session.scalar(
            select(RetrievalChunk).where(RetrievalChunk.document_id == document.id)
        )
        assert chunk is not None
        embedding = session.scalar(
            select(ChunkEmbedding).where(ChunkEmbedding.chunk_id == chunk.id)
        )
        assert embedding is not None
        assert embedding.vector_dim == len(embedding.vector_payload)


def test_repeated_materialization_replaces_chunks_without_orphans(tmp_path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        artifact = RunService(session).record_chapter_artifact(branch.id, 1, _artifact_payload())
        service = RetrievalService(session, Settings())
        first = service.materialize_for_artifact(artifact.id)
        first_chunk_count = session.query(RetrievalChunk).count()
        first_embedding_count = session.query(ChunkEmbedding).count()
        second = service.materialize_for_artifact(artifact.id)
        assert first.id == second.id
        assert session.query(RetrievalChunk).count() == first_chunk_count
        assert session.query(ChunkEmbedding).count() == first_embedding_count


def test_search_branch_returns_hits_for_materialized_document(tmp_path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        artifact = RunService(session).record_chapter_artifact(branch.id, 1, _artifact_payload())
        service = RetrievalService(session, Settings())
        service.materialize_for_artifact(artifact.id)
        hits = service.search_branch(branch.id, '命格')
        assert hits
        assert hits[0].chapter_index == 1


def test_default_fts_config_is_simple_on_sqlite(tmp_path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        service = RetrievalService(session, Settings())
        assert service._fts_config_name() == 'simple'
