from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from novel_analyzer.embedding.service import get_embedding_provider
from novel_analyzer.config.settings import Settings
from novel_analyzer.database.models import ChunkEmbedding, RetrievalChunk, RetrievalDocument
from novel_analyzer.database.session import create_schema
from novel_analyzer.rerank.service import get_rerank_provider
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.retrieval_service import (
    RetrievalHit,
    RetrievalService,
)
from novel_analyzer.services.run_service import RunService


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    return Session(engine)


def _artifact_payload() -> dict[str, object]:
    return {
        "chapter_index": 1,
        "normalized_title": "命格初现",
        "chapter_summary": "卫图觉醒命格",
        "key_entities": ["卫图"],
        "key_events": ["觉醒命格"],
        "continuity_notes": ["开启求仙主线"],
        "dimensions": [],
        "writer_learning_notes": [],
        "unsupported_inferences": [],
        "ambiguous_points": [],
        "needs_human_review": False,
    }


def test_retrieval_materialization_creates_document_chunk_and_embedding(
    tmp_path: Path,
) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        artifact = RunService(session).record_chapter_artifact(branch.id, 1, _artifact_payload())
        document = RetrievalService(
            session, Settings(embedding_backend="stub")
        ).materialize_for_artifact(artifact.id)
        loaded_document = session.scalar(
            select(RetrievalDocument).where(RetrievalDocument.id == document.id)
        )
        assert loaded_document is not None
        assert loaded_document.keyword_list == ["卫图", "觉醒命格"]
        chunk = session.scalar(
            select(RetrievalChunk).where(RetrievalChunk.document_id == document.id)
        )
        assert chunk is not None
        embedding = session.scalar(
            select(ChunkEmbedding).where(ChunkEmbedding.chunk_id == chunk.id)
        )
        assert embedding is not None
        assert embedding.vector_dim == len(embedding.vector_payload)


def test_repeated_materialization_replaces_chunks_without_orphans(tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        artifact = RunService(session).record_chapter_artifact(branch.id, 1, _artifact_payload())
        service = RetrievalService(session, Settings(embedding_backend="stub"))
        first = service.materialize_for_artifact(artifact.id)
        first_chunk_count = session.query(RetrievalChunk).count()
        first_embedding_count = session.query(ChunkEmbedding).count()
        second = service.materialize_for_artifact(artifact.id)
        assert first.id == second.id
        assert session.query(RetrievalChunk).count() == first_chunk_count
        assert session.query(ChunkEmbedding).count() == first_embedding_count


def test_embedding_and_rerank_providers_are_cached() -> None:
    settings = Settings(embedding_backend="stub", rerank_model_name="")
    first_embedding = get_embedding_provider(settings)
    second_embedding = get_embedding_provider(settings)
    assert first_embedding is second_embedding

    first_rerank = get_rerank_provider(settings)
    second_rerank = get_rerank_provider(settings)
    assert first_rerank is second_rerank


def test_search_branch_requires_postgresql_runtime(tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        artifact = RunService(session).record_chapter_artifact(branch.id, 1, _artifact_payload())
        service = RetrievalService(session, Settings(embedding_backend="stub"))
        service.materialize_for_artifact(artifact.id)
        with pytest.raises(RuntimeError, match="Only PostgreSQL is supported"):
            service.search_branch(branch.id, "命格")


def test_default_fts_config_remains_simple_without_pg_jieba(tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        service = RetrievalService(session, Settings())
        assert service._fts_config_name() == "simple"


def test_apply_rerank_reorders_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeRerankProvider:
        seen_docs: list[str] | None = None

        def rerank(self, query: str, documents: list[str]) -> list[float]:
            _ = query
            self.seen_docs = documents
            return [0.2, 0.9]

    with _session() as session:
        provider = _FakeRerankProvider()
        service = RetrievalService(session, Settings(rerank_model_name="fake-model"))
        monkeypatch.setattr(
            "novel_analyzer.services.retrieval_service.get_rerank_provider",
            lambda settings=None: provider,
        )
        hits = [
            RetrievalHit(
                chapter_index=1, title="一", summary_text="弱相关", score=0.8, keyword_list=["卫图"]
            ),
            RetrievalHit(
                chapter_index=2, title="二", summary_text="强相关", score=0.1, keyword_list=["命格"]
            ),
        ]
        reranked, rerank_applied = service._apply_rerank("命格", hits, limit=2)
        assert rerank_applied is True
        assert [hit.chapter_index for hit in reranked] == [2, 1]
        assert reranked[0].score == pytest.approx(0.9)
        assert reranked[1].score == pytest.approx(0.2)
        assert provider.seen_docs is not None
        assert len(provider.seen_docs) == 2


def test_apply_rerank_caps_candidate_count(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeRerankProvider:
        seen_docs: list[str] | None = None

        def rerank(self, query: str, documents: list[str]) -> list[float]:
            _ = query
            self.seen_docs = documents
            return [float(index) for index, _ in enumerate(documents, start=1)]

    with _session() as session:
        provider = _FakeRerankProvider()
        service = RetrievalService(session, Settings(rerank_model_name="fake-model"))
        monkeypatch.setattr(
            "novel_analyzer.services.retrieval_service.get_rerank_provider",
            lambda settings=None: provider,
        )
        hits = [
            RetrievalHit(
                chapter_index=index,
                title=f"第{index}章",
                summary_text=f"正文{index}",
                score=1.0 / index,
                keyword_list=[],
            )
            for index in range(1, 21)
        ]
        reranked, rerank_applied = service._apply_rerank("命格", hits, limit=5)
        assert rerank_applied is True
        assert provider.seen_docs is not None
        assert len(provider.seen_docs) == service.MAX_RERANK_CANDIDATES
        assert len(reranked) == 5


def test_hit_rerank_text_is_capped() -> None:
    hit = RetrievalHit(
        chapter_index=1,
        title="标题",
        summary_text="很长的正文" * 200,
        score=1.0,
        keyword_list=["关键词A", "关键词B"],
    )
    text = RetrievalService._hit_rerank_text(hit)
    assert len(text) <= RetrievalService.RERANK_TEXT_CHAR_LIMIT + 1
    assert text.endswith("…")


def test_apply_rerank_falls_back_when_provider_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenRerankProvider:
        def rerank(self, query: str, documents: list[str]) -> list[float]:
            _ = query, documents
            raise RuntimeError("rerank unavailable")

    with _session() as session:
        service = RetrievalService(session, Settings(rerank_model_name="fake-model"))
        monkeypatch.setattr(
            "novel_analyzer.services.retrieval_service.get_rerank_provider",
            lambda settings=None: _BrokenRerankProvider(),
        )
        hits = [
            RetrievalHit(
                chapter_index=1,
                title="一",
                summary_text="命格出现",
                score=0.8,
                keyword_list=["卫图"],
            ),
            RetrievalHit(
                chapter_index=2,
                title="二",
                summary_text="资源铺垫",
                score=0.1,
                keyword_list=["资源"],
            ),
        ]
        reranked, rerank_applied = service._apply_rerank("命格", hits, limit=2)
        assert rerank_applied is False
        assert [hit.chapter_index for hit in reranked] == [1, 2]
        assert reranked[0].score == pytest.approx(0.8)
        assert reranked[1].score == pytest.approx(0.1)


def test_reciprocal_rank_fuse_promotes_cross_route_consensus() -> None:
    route_hits = [
        (
            "fts",
            [
                RetrievalHit(
                    chapter_index=1,
                    title="一",
                    summary_text="命格初现",
                    score=10.0,
                    keyword_list=["命格"],
                ),
                RetrievalHit(
                    chapter_index=2,
                    title="二",
                    summary_text="弱相关",
                    score=9.0,
                    keyword_list=["卫图"],
                ),
            ],
        ),
        (
            "keyword",
            [
                RetrievalHit(
                    chapter_index=3,
                    title="三",
                    summary_text="候选",
                    score=100.0,
                    keyword_list=["资源"],
                ),
                RetrievalHit(
                    chapter_index=1,
                    title="一",
                    summary_text="命格初现",
                    score=1.0,
                    keyword_list=["命格"],
                ),
            ],
        ),
    ]

    fused = RetrievalService._reciprocal_rank_fuse(route_hits, limit=3, rank_constant=10)

    assert [hit.chapter_index for hit in fused] == [1, 3, 2]
    assert fused[0].score == pytest.approx((1 / 11) + (1 / 12))
    assert fused[0].summary_text == "命格初现"


def test_search_branch_with_diagnostics_preserves_raw_and_reranked_views(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _session() as session:
        service = RetrievalService(session, Settings(embedding_backend="stub"))
        raw_hits = [
            RetrievalHit(
                chapter_index=1, title="一", summary_text="弱相关", score=0.8, keyword_list=["卫图"]
            ),
            RetrievalHit(
                chapter_index=2, title="二", summary_text="强相关", score=0.1, keyword_list=["命格"]
            ),
        ]
        reranked_hits = [
            RetrievalHit(
                chapter_index=2,
                title="二",
                summary_text="强相关",
                score=0.95,
                keyword_list=["命格"],
            ),
            RetrievalHit(
                chapter_index=1,
                title="一",
                summary_text="弱相关",
                score=0.25,
                keyword_list=["卫图"],
            ),
        ]

        monkeypatch.setattr(
            service,
            "_search_branch_routes",
            lambda branch_id, query, limit: [("fts", raw_hits)],
        )
        monkeypatch.setattr(
            service,
            "_apply_rerank",
            lambda query, hits, *, limit: (reranked_hits, True),
        )

        diagnostics = service.search_branch_with_diagnostics("branch-1", "命格", limit=2)
        assert diagnostics.query == "命格"
        assert diagnostics.rerank_applied is True
        assert diagnostics.fusion_applied is False
        assert diagnostics.route_counts == {"fts": 2}
        assert diagnostics.route_diagnostics is not None
        assert diagnostics.route_diagnostics[0].route == "fts"
        assert diagnostics.route_diagnostics[0].hit_count == 2
        assert diagnostics.raw_latency_ms >= 0.0
        assert diagnostics.rerank_latency_ms >= 0.0
        assert diagnostics.raw_hits == raw_hits
        assert diagnostics.reranked_hits == reranked_hits


def test_search_branch_routes_skip_vector_when_lexical_coverage_is_enough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _session() as session:
        service = RetrievalService(session, Settings(rerank_backend="disabled"))
        monkeypatch.setattr(service.session.bind.dialect, "name", "postgresql", raising=False)
        lexical_rows = [
            {
                "chapter_index": index,
                "title": f"第{index}章",
                "summary_text": f"正文{index}",
                "keyword_list": [],
                "score": 1.0 / index,
            }
            for index in range(1, 6)
        ]

        monkeypatch.setattr(service, "_fts_config_name", lambda: "simple")

        def _fake_execute(stmt, params=None):  # noqa: ANN001
            sql = str(stmt)
            class _Result:
                def __init__(self, rows):
                    self._rows = rows
                def mappings(self):
                    return self
                def all(self):
                    return self._rows
            if "bm25_vector @@" in sql:
                return _Result(lexical_rows[:1])
            if "similarity(title || ' ' || bm25_text" in sql:
                return _Result(lexical_rows)
            if "ILIKE" in sql:
                return _Result(lexical_rows)
            return _Result([])

        monkeypatch.setattr(service.session, "execute", _fake_execute)
        monkeypatch.setattr(service, "_keyword_overlap_fallback", lambda branch_id, query, limit: [])
        monkeypatch.setattr(service, "_entity_exact_route", lambda branch_id, query, limit: [])

        def _fail_vector(*args, **kwargs):  # noqa: ANN002, ANN003
            raise AssertionError("vector route should be skipped")

        monkeypatch.setattr(service, "_vector_route", _fail_vector)
        routes, diagnostics = service._search_branch_routes_with_diagnostics("branch-x", "命格", limit=5)
        assert routes
        assert any(item.route == "vector" and item.hit_count == 0 for item in diagnostics)


def test_rrf_fusion_prioritizes_consensus_hits_without_changing_single_lane() -> None:
    lane_one = [
        RetrievalHit(
            chapter_index=1,
            title="一",
            summary_text="命格弱相关",
            score=0.95,
            keyword_list=["命格"],
        ),
        RetrievalHit(
            chapter_index=2, title="二", summary_text="资源铺垫", score=0.80, keyword_list=["资源"]
        ),
    ]
    lane_two = [
        RetrievalHit(
            chapter_index=2, title="二", summary_text="资源铺垫", score=0.30, keyword_list=["资源"]
        ),
        RetrievalHit(
            chapter_index=3, title="三", summary_text="外门线索", score=0.90, keyword_list=["外门"]
        ),
    ]

    assert RetrievalService._fuse_recall_lists([lane_one], limit=2) == lane_one

    fused = RetrievalService._fuse_recall_lists([lane_one, lane_two], limit=3, k=60)
    assert [hit.chapter_index for hit in fused] == [2, 1, 3]
    assert fused[0].score > fused[1].score
    assert fused[0].summary_text == "资源铺垫"


def test_search_branch_uses_rrf_hook_before_rerank(monkeypatch: pytest.MonkeyPatch) -> None:
    with _session() as session:
        service = RetrievalService(session, Settings(rerank_backend="disabled"))
        lane_one = [
            RetrievalHit(
                chapter_index=1, title="一", summary_text="命格弱相关", score=0.95, keyword_list=[]
            ),
            RetrievalHit(
                chapter_index=2, title="二", summary_text="命格强相关", score=0.70, keyword_list=[]
            ),
        ]
        lane_two = [
            RetrievalHit(
                chapter_index=2, title="二", summary_text="命格强相关", score=0.60, keyword_list=[]
            ),
            RetrievalHit(
                chapter_index=3, title="三", summary_text="旁支", score=0.90, keyword_list=[]
            ),
        ]
        monkeypatch.setattr(
            service,
            "_collect_recall_candidates",
            lambda branch_id, query, limit: [lane_one, lane_two],
        )
        monkeypatch.setattr(
            service, "_apply_rerank", lambda query, hits, *, limit: (hits[:limit], False)
        )

        hits = service.search_branch("branch-rrf", "命格", limit=2)
        assert [hit.chapter_index for hit in hits] == [2, 1]

        diagnostics = service.search_branch_with_diagnostics("branch-rrf", "命格", limit=2)
        assert diagnostics.rerank_applied is False
        assert [hit.chapter_index for hit in diagnostics.raw_hits] == [2, 1, 3]
        assert diagnostics.route_counts == {"route_1": 2, "route_2": 2}
        assert [
            item.route for item in diagnostics.route_diagnostics or []
        ] == ["route_1", "route_2"]


def test_search_branch_public_contract_stays_plain_hit_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _session() as session:
        service = RetrievalService(session, Settings(rerank_backend="disabled"))
        lane = [
            RetrievalHit(
                chapter_index=7,
                title="七",
                summary_text="命格兑现",
                score=0.9,
                keyword_list=["命格"],
            )
        ]
        monkeypatch.setattr(
            service,
            "_collect_recall_candidates",
            lambda branch_id, query, limit: [lane],
        )

        hits = service.search_branch("branch-public", "命格", limit=1)

        assert isinstance(hits, list)
        assert hits == lane
        assert set(hits[0].__dataclass_fields__) == {
            "chapter_index",
            "title",
            "summary_text",
            "score",
            "keyword_list",
        }


def test_entity_exact_route_returns_fact_backed_chapters(tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        service = RetrievalService(session, Settings(embedding_backend="stub"))
        for idx, title, summary, entities in [
            (1, "命格初现", "卫图觉醒命格", ["卫图", "命格"]),
            (2, "资源铺垫", "二姑帮卫图筹措资源", ["二姑", "资源"]),
        ]:
            artifact = RunService(session).record_chapter_artifact(
                branch.id,
                idx,
                {
                    "chapter_index": idx,
                    "normalized_title": title,
                    "chapter_summary": summary,
                    "key_entities": entities,
                    "key_events": [summary],
                    "continuity_notes": [],
                    "writer_learning_notes": [],
                    "unsupported_inferences": [],
                    "ambiguous_points": [],
                    "needs_human_review": False,
                    "dimensions": [],
                },
            )
            service.materialize_for_artifact(artifact.id)
            from novel_analyzer.services.fact_service import FactService
            FactService(session).materialize_for_artifact(artifact.id)

        hits = service._entity_exact_route(branch.id, "卫图", limit=5)  # noqa: SLF001
        assert hits
        assert hits[0].chapter_index == 1
        assert "卫图" in hits[0].summary_text or hits[0].title == "命格初现"


def test_vector_route_uses_embedding_similarity(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeProvider:
        def embed_texts(self, texts: list[str]) -> list[list[float]]:
            _ = texts
            return [[1.0, 0.0]]

    with _session() as session:
        doc_1 = RetrievalDocument(
            branch_id='branch-v',
            chapter_index=1,
            title='命格初现',
            summary_text='卫图觉醒命格',
            bm25_text='卫图觉醒命格',
            keyword_list=[],
            query_hints=[],
            materialization_status='ready',
        )
        doc_2 = RetrievalDocument(
            branch_id='branch-v',
            chapter_index=2,
            title='资源铺垫',
            summary_text='二姑筹措资源',
            bm25_text='二姑筹措资源',
            keyword_list=[],
            query_hints=[],
            materialization_status='ready',
        )
        session.add_all([doc_1, doc_2])
        session.flush()
        chunk_1 = RetrievalChunk(
            document_id=doc_1.id,
            chunk_order=1,
            text='卫图觉醒命格',
            start_offset=0,
            end_offset=6,
            embedding_status='ready',
            keyword_list=[],
        )
        chunk_2 = RetrievalChunk(
            document_id=doc_2.id,
            chunk_order=1,
            text='二姑筹措资源',
            start_offset=0,
            end_offset=6,
            embedding_status='ready',
            keyword_list=[],
        )
        session.add_all([chunk_1, chunk_2])
        session.flush()
        session.add_all(
            [
                ChunkEmbedding(
                    chunk_id=chunk_1.id,
                    model_name='stub',
                    vector_dim=2,
                    vector_payload=[1.0, 0.0],
                    l2_norm=1.0,
                    status='ready',
                ),
                ChunkEmbedding(
                    chunk_id=chunk_2.id,
                    model_name='stub',
                    vector_dim=2,
                    vector_payload=[0.0, 1.0],
                    l2_norm=1.0,
                    status='ready',
                ),
            ]
        )
        session.commit()
        monkeypatch.setattr(
            'novel_analyzer.services.retrieval_service.get_embedding_provider',
            lambda settings=None: _FakeProvider(),
        )
        service = RetrievalService(session, Settings(embedding_backend='stub'))
        hits = service._vector_route('branch-v', '命格', limit=5)  # noqa: SLF001
        assert hits
        assert hits[0].chapter_index == 1
