"""Retrieval materialization from validated chapter JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import (
    ChapterArtifact,
    ChunkEmbedding,
    RetrievalChunk,
    RetrievalDocument,
)
from novel_analyzer.embedding.service import get_embedding_provider
from novel_analyzer.rerank.service import DisabledRerankProvider, get_rerank_provider


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    """A deterministic retrieval chunk draft."""

    chunk_order: int
    text: str
    start_offset: int
    end_offset: int
    keywords: list[str]


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    """A normalized search hit returned by the query service."""

    chapter_index: int
    title: str
    summary_text: str
    score: float
    keyword_list: list[str]


@dataclass(frozen=True, slots=True)
class RetrievalRouteDiagnostics:
    """Per-route retrieval diagnostics for latency and contribution checks."""

    route: str
    hit_count: int
    latency_ms: float


@dataclass(frozen=True, slots=True)
class RetrievalSearchDiagnostics:
    """Raw, fused, and reranked retrieval views for inspection/evaluation."""

    query: str
    raw_hits: list[RetrievalHit]
    reranked_hits: list[RetrievalHit]
    rerank_applied: bool
    fusion_applied: bool = False
    route_counts: dict[str, int] | None = None


class RetrievalService:
    """Materializes retrieval-friendly rows from validated chapter analysis."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    @staticmethod
    def _normalize_keywords(payload: dict[str, Any]) -> list[str]:
        keywords = []
        for item in payload.get("key_entities", []):
            if isinstance(item, str) and item.strip():
                keywords.append(item.strip())
        for item in payload.get("key_events", []):
            if isinstance(item, str) and item.strip():
                keywords.append(item.strip())
        seen: set[str] = set()
        ordered: list[str] = []
        for item in keywords:
            if item not in seen:
                seen.add(item)
                ordered.append(item)
        return ordered

    @staticmethod
    def _query_hints(payload: dict[str, Any], title: str) -> list[str]:
        hints = [f"第{payload.get('chapter_index', '?')}章 {title} 讲了什么"]
        for item in payload.get("key_entities", [])[:3]:
            if isinstance(item, str) and item.strip():
                hints.append(f"{item.strip()} 在这一章发生了什么")
        return hints

    @staticmethod
    def _bm25_text(payload: dict[str, Any], title: str) -> str:
        parts: list[str] = [title, payload.get("chapter_summary", "")]
        parts.extend(item for item in payload.get("key_events", []) if isinstance(item, str))
        parts.extend(item for item in payload.get("continuity_notes", []) if isinstance(item, str))
        for dimension in payload.get("dimensions", []):
            if isinstance(dimension, dict):
                parts.append(str(dimension.get("dimension", "")))
                parts.append(str(dimension.get("summary", "")))
                parts.extend(
                    str(item) for item in dimension.get("evidence", []) if isinstance(item, str)
                )
        return "\n".join(part.strip() for part in parts if part and str(part).strip())

    @staticmethod
    def _chunk_text(bm25_text: str, keywords: list[str], chunk_size: int = 900) -> list[ChunkDraft]:
        source = bm25_text.strip()
        if not source:
            return []
        chunks: list[ChunkDraft] = []
        offset = 0
        order = 1
        while offset < len(source):
            end = min(len(source), offset + chunk_size)
            chunk_text = source[offset:end]
            chunks.append(
                ChunkDraft(
                    chunk_order=order,
                    text=chunk_text,
                    start_offset=offset,
                    end_offset=end,
                    keywords=keywords[:12],
                )
            )
            offset = end
            order += 1
        return chunks

    @staticmethod
    def _embedding_norm(vector: list[float]) -> float:
        return float(sum(value * value for value in vector) ** 0.5)

    @staticmethod
    def _coerce_keywords(raw: Any) -> list[str]:
        if isinstance(raw, list):
            return [str(item) for item in raw]
        if isinstance(raw, str):
            try:
                decoded = json.loads(raw)
            except Exception:  # noqa: BLE001
                return [raw]
            if isinstance(decoded, list):
                return [str(item) for item in decoded]
            return [str(decoded)]
        return [str(item) for item in (raw or [])]

    @classmethod
    def _row_to_hit(cls, row: RowMapping) -> RetrievalHit:
        return RetrievalHit(
            chapter_index=int(row["chapter_index"]),
            title=str(row["title"]),
            summary_text=str(row["summary_text"]),
            score=float(row["score"]),
            keyword_list=cls._coerce_keywords(row["keyword_list"]),
        )

    @staticmethod
    def _hit_rerank_text(hit: RetrievalHit) -> str:
        keywords = ", ".join(hit.keyword_list[:8])
        return "\n".join(
            part for part in [hit.title.strip(), hit.summary_text.strip(), keywords.strip()] if part
        )

    @staticmethod
    def _fuse_recall_lists(
        ranked_lists: list[list[RetrievalHit]],
        *,
        limit: int,
        k: int = 60,
    ) -> list[RetrievalHit]:
        """Fuse multiple recall lanes with reciprocal-rank fusion.

        A single recall lane is returned unchanged to keep the existing QA/search score
        contract stable. Multi-lane callers get deterministic chapter-level de-duping and
        fused scores without needing to change the downstream rerank interface.
        """

        non_empty_lists = [hits for hits in ranked_lists if hits]
        if not non_empty_lists:
            return []
        if len(non_empty_lists) == 1:
            return non_empty_lists[0][:limit]

        fused_scores: dict[int, float] = {}
        best_hits: dict[int, RetrievalHit] = {}
        best_source_scores: dict[int, float] = {}
        best_ranks: dict[int, int] = {}
        for hits in non_empty_lists:
            seen_in_lane: set[int] = set()
            for rank, hit in enumerate(hits, start=1):
                if hit.chapter_index in seen_in_lane:
                    continue
                seen_in_lane.add(hit.chapter_index)
                fused_scores[hit.chapter_index] = fused_scores.get(hit.chapter_index, 0.0) + 1.0 / (
                    k + rank
                )
                previous_best_score = best_source_scores.get(hit.chapter_index, float("-inf"))
                previous_best_rank = best_ranks.get(hit.chapter_index, 10**9)
                if hit.score > previous_best_score or (
                    hit.score == previous_best_score and rank < previous_best_rank
                ):
                    best_hits[hit.chapter_index] = hit
                    best_source_scores[hit.chapter_index] = hit.score
                    best_ranks[hit.chapter_index] = rank

        ordered_chapter_indexes = sorted(
            fused_scores,
            key=lambda chapter_index: (
                -fused_scores[chapter_index],
                best_ranks[chapter_index],
                chapter_index,
            ),
        )
        return [
            RetrievalHit(
                chapter_index=best_hits[chapter_index].chapter_index,
                title=best_hits[chapter_index].title,
                summary_text=best_hits[chapter_index].summary_text,
                score=fused_scores[chapter_index],
                keyword_list=best_hits[chapter_index].keyword_list,
            )
            for chapter_index in ordered_chapter_indexes[:limit]
        ]

    def _apply_rerank(
        self,
        query: str,
        hits: list[RetrievalHit],
        *,
        limit: int,
    ) -> tuple[list[RetrievalHit], bool]:
        if not hits:
            return hits, False
        provider = get_rerank_provider(self.settings)
        if isinstance(provider, DisabledRerankProvider):
            return hits[:limit], False
        try:
            rerank_scores = provider.rerank(
                query,
                [self._hit_rerank_text(hit) for hit in hits],
            )
        except Exception:
            return hits[:limit], False
        reranked = sorted(
            zip(hits, rerank_scores, strict=True),
            key=lambda item: (-item[1], -item[0].score, item[0].chapter_index),
        )
        return (
            [
                RetrievalHit(
                    chapter_index=hit.chapter_index,
                    title=hit.title,
                    summary_text=hit.summary_text,
                    score=float(score),
                    keyword_list=hit.keyword_list,
                )
                for hit, score in reranked[:limit]
            ],
            True,
        )

    def _fts_config_name(self) -> str:
        if self.session.bind is None or self.session.bind.dialect.name != "postgresql":
            return "simple"
        row = self.session.execute(
            text(
                "SELECT cfgname FROM pg_ts_config "
                "WHERE cfgname IN ('jiebacfg','jiebaqry','simple') "
                "ORDER BY CASE cfgname "
                "WHEN 'jiebacfg' THEN 1 "
                "WHEN 'jiebaqry' THEN 2 "
                "ELSE 3 END LIMIT 1"
            )
        ).scalar_one_or_none()
        return str(row or "simple")

    def _keyword_overlap_fallback(
        self,
        branch_id: str,
        query: str,
        limit: int,
    ) -> list[RetrievalHit]:
        rows = (
            self.session.execute(
                text(
                    """
                SELECT chapter_index, title, summary_text, keyword_list
                FROM retrieval_documents
                WHERE branch_id = :branch_id
                ORDER BY chapter_index ASC
                """
                ),
                {"branch_id": branch_id},
            )
            .mappings()
            .all()
        )
        hits: list[RetrievalHit] = []
        for row in rows:
            keywords = self._coerce_keywords(row["keyword_list"])
            score = 0.0
            for keyword in keywords:
                word = str(keyword)
                if word and word in query:
                    score += 1.0
                elif query and query in word:
                    score += 0.5
            if score > 0.0:
                hits.append(
                    RetrievalHit(
                        chapter_index=int(row["chapter_index"]),
                        title=str(row["title"]),
                        summary_text=str(row["summary_text"]),
                        score=score,
                        keyword_list=keywords,
                    )
                )
        hits.sort(key=lambda item: (-item.score, item.chapter_index))
        return hits[:limit]

    def materialize_for_artifact(self, artifact_id: str) -> RetrievalDocument:
        """Create/update retrieval rows for a chapter artifact."""

        artifact = self.session.scalar(
            select(ChapterArtifact).where(ChapterArtifact.id == artifact_id)
        )
        if artifact is None:
            raise ValueError(f"Unknown artifact_id: {artifact_id}")

        payload = artifact.payload_json
        title = str(payload.get("normalized_title", ""))
        keywords = self._normalize_keywords(payload)
        query_hints = self._query_hints(payload, title)
        bm25_text = self._bm25_text(payload, title)

        document = self.session.scalar(
            select(RetrievalDocument)
            .where(RetrievalDocument.branch_id == artifact.branch_id)
            .where(RetrievalDocument.chapter_index == artifact.chapter_index)
        )
        if document is None:
            document = RetrievalDocument(
                branch_id=artifact.branch_id,
                chapter_index=artifact.chapter_index,
                title=title,
                summary_text=str(payload.get("chapter_summary", "")),
                bm25_text=bm25_text,
                keyword_list=keywords,
                query_hints=query_hints,
            )
            self.session.add(document)
            self.session.flush()
        else:
            document.title = title
            document.summary_text = str(payload.get("chapter_summary", ""))
            document.bm25_text = bm25_text
            document.keyword_list = keywords
            document.query_hints = query_hints
            document.materialization_status = "ready"
            for chunk in list(document.chunks):
                self.session.delete(chunk)
            self.session.flush()

        chunk_drafts = self._chunk_text(bm25_text, keywords)
        provider = get_embedding_provider(self.settings)
        vectors = (
            provider.embed_texts([draft.text for draft in chunk_drafts]) if chunk_drafts else []
        )

        for draft, vector in zip(chunk_drafts, vectors, strict=True):
            chunk = RetrievalChunk(
                document_id=document.id,
                chunk_order=draft.chunk_order,
                text=draft.text,
                start_offset=draft.start_offset,
                end_offset=draft.end_offset,
                embedding_status="ready",
                keyword_list=draft.keywords,
            )
            self.session.add(chunk)
            self.session.flush()
            self.session.add(
                ChunkEmbedding(
                    chunk_id=chunk.id,
                    model_name=self.settings.embedding_model_name,
                    vector_dim=len(vector),
                    vector_payload=vector,
                    l2_norm=self._embedding_norm(vector),
                    status="ready",
                )
            )

        self.session.commit()
        self.session.refresh(document)
        return document

    @staticmethod
    def _reciprocal_rank_fuse(
        route_hits: list[tuple[str, list[RetrievalHit]]],
        *,
        limit: int,
        rank_constant: int = 60,
    ) -> list[RetrievalHit]:
        """Fuse multiple ranked retrieval routes with reciprocal rank fusion.

        Each route contributes rank-only evidence so heterogeneous scores from
        FTS, trigram similarity, LIKE fallback, and semantic keyword matching do
        not need calibration before rerank. Hits are keyed by chapter because the
        public QA/search contract returns chapter-level evidence.
        """

        if not route_hits:
            return []
        if len(route_hits) == 1:
            return route_hits[0][1][:limit]

        fused_scores: dict[int, float] = {}
        best_hits: dict[int, RetrievalHit] = {}
        best_source_scores: dict[int, float] = {}
        for _route_name, hits in route_hits:
            for rank, hit in enumerate(hits, start=1):
                fused_scores[hit.chapter_index] = fused_scores.get(hit.chapter_index, 0.0) + (
                    1.0 / (rank_constant + rank)
                )
                previous_score = best_source_scores.get(hit.chapter_index)
                if previous_score is None or hit.score > previous_score:
                    best_source_scores[hit.chapter_index] = hit.score
                    best_hits[hit.chapter_index] = hit

        fused_hits = [
            RetrievalHit(
                chapter_index=hit.chapter_index,
                title=hit.title,
                summary_text=hit.summary_text,
                score=fused_scores[hit.chapter_index],
                keyword_list=hit.keyword_list,
            )
            for hit in best_hits.values()
        ]
        fused_hits.sort(key=lambda item: (-item.score, item.chapter_index))
        return fused_hits[:limit]

    def _search_branch_routes(
        self,
        branch_id: str,
        query: str,
        limit: int,
    ) -> list[tuple[str, list[RetrievalHit]]]:
        """Return raw retrieval routes before RRF and rerank ordering."""
        if self.session.bind is None:
            raise ValueError("session is not bound")
        dialect = self.session.bind.dialect.name
        fetch_limit = max(limit * 4, limit)
        if dialect == "postgresql":
            routes: list[tuple[str, list[RetrievalHit]]] = []
            config_name = self._fts_config_name()
            fulltext_sql = text(
                f"""
                SELECT
                    chapter_index,
                    title,
                    summary_text,
                    keyword_list,
                    (
                        ts_rank_cd(bm25_vector, plainto_tsquery('{config_name}', :query)) * 0.8 +
                        similarity(title || ' ' || bm25_text, :query) * 0.2
                    ) AS score
                FROM retrieval_documents
                WHERE branch_id = :branch_id
                  AND bm25_vector @@ plainto_tsquery('{config_name}', :query)
                ORDER BY score DESC, chapter_index ASC
                LIMIT :limit
                """
            )
            rows = (
                self.session.execute(
                    fulltext_sql,
                    {"branch_id": branch_id, "query": query, "limit": fetch_limit},
                )
                .mappings()
                .all()
            )
            if rows:
                routes.append(("fts", [self._row_to_hit(row) for row in rows]))

            fallback_rows = (
                self.session.execute(
                    text(
                        """
                    SELECT
                        chapter_index,
                        title,
                        summary_text,
                        keyword_list,
                        similarity(title || ' ' || bm25_text, :query) AS score
                    FROM retrieval_documents
                    WHERE branch_id = :branch_id
                      AND similarity(title || ' ' || bm25_text, :query) > 0.0
                    ORDER BY score DESC, chapter_index ASC
                    LIMIT :limit
                    """
                    ),
                    {"branch_id": branch_id, "query": query, "limit": fetch_limit},
                )
                .mappings()
                .all()
            )
            if fallback_rows:
                routes.append(("similarity", [self._row_to_hit(row) for row in fallback_rows]))

            tokens = [token.strip() for token in query.split() if token.strip()]
            if not tokens:
                tokens = [query]
            clauses: list[str] = []
            params: dict[str, object] = {"branch_id": branch_id, "limit": limit}
            for index, token in enumerate(tokens):
                key = f"token_{index}"
                clauses.append(f"title ILIKE :{key} OR bm25_text ILIKE :{key}")
                params[key] = f"%{token}%"
            sql_like = text(
                f"""
                SELECT
                    chapter_index,
                    title,
                    summary_text,
                    keyword_list,
                    1.0 AS score
                FROM retrieval_documents
                WHERE branch_id = :branch_id
                  AND ({" OR ".join(clauses)})
                ORDER BY chapter_index ASC
                LIMIT :limit
                """
            )
            params["limit"] = fetch_limit
            like_rows = self.session.execute(sql_like, params).mappings().all()
            if like_rows:
                routes.append(("like", [self._row_to_hit(row) for row in like_rows]))
            keyword_hits = self._keyword_overlap_fallback(branch_id, query, fetch_limit)
            if keyword_hits:
                routes.append(("keyword", keyword_hits))
            return routes

        raise RuntimeError(
            "Only PostgreSQL is supported for retrieval search; SQLite fallback has been removed."
        )

    def _collect_recall_candidates(
        self,
        branch_id: str,
        query: str,
        limit: int,
    ) -> list[list[RetrievalHit]]:
        """Collect ranked recall candidates from each retrieval route."""

        return [hits for _route_name, hits in self._search_branch_routes(branch_id, query, limit)]

    def _search_branch_raw(self, branch_id: str, query: str, limit: int) -> list[RetrievalHit]:
        """Return RRF-fused retrieval hits before rerank ordering."""

        return self._fuse_recall_lists(
            self._collect_recall_candidates(branch_id, query, limit),
            limit=max(limit * 4, limit),
        )

    def search_branch(self, branch_id: str, query: str, limit: int = 5) -> list[RetrievalHit]:
        """Search retrieval documents for a branch."""

        raw_hits = self._search_branch_raw(branch_id, query, limit)
        reranked_hits, _ = self._apply_rerank(query, raw_hits, limit=limit)
        return reranked_hits

    def search_branch_with_diagnostics(
        self,
        branch_id: str,
        query: str,
        limit: int = 5,
    ) -> RetrievalSearchDiagnostics:
        """Return raw and reranked hits for inspection."""

        try:
            routes = self._search_branch_routes(branch_id, query, limit)
        except RuntimeError:
            routes = [
                (f"route_{index + 1}", hits)
                for index, hits in enumerate(
                    self._collect_recall_candidates(branch_id, query, limit)
                )
            ]
        raw_hits = self._fuse_recall_lists(
            [hits for _route_name, hits in routes],
            limit=max(limit * 4, limit),
        )
        reranked_hits, rerank_applied = self._apply_rerank(query, raw_hits, limit=limit)
        return RetrievalSearchDiagnostics(
            query=query,
            raw_hits=raw_hits,
            reranked_hits=reranked_hits,
            rerank_applied=rerank_applied,
            fusion_applied=len(routes) > 1,
            route_counts={route_name: len(hits) for route_name, hits in routes},
        )
