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
                    str(item)
                    for item in dimension.get("evidence", [])
                    if isinstance(item, str)
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

    def _fts_config_name(self) -> str:
        if self.session.bind is None or self.session.bind.dialect.name != 'postgresql':
            return 'simple'
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
        return str(row or 'simple')


    def _keyword_overlap_fallback(
        self,
        branch_id: str,
        query: str,
        limit: int,
    ) -> list[RetrievalHit]:
        rows = self.session.execute(
            text(
                """
                SELECT chapter_index, title, summary_text, keyword_list
                FROM retrieval_documents
                WHERE branch_id = :branch_id
                ORDER BY chapter_index ASC
                """
            ),
            {"branch_id": branch_id},
        ).mappings().all()
        hits: list[RetrievalHit] = []
        for row in rows:
            keywords = self._coerce_keywords(row['keyword_list'])
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
                        chapter_index=int(row['chapter_index']),
                        title=str(row['title']),
                        summary_text=str(row['summary_text']),
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

    def search_branch(self, branch_id: str, query: str, limit: int = 5) -> list[RetrievalHit]:
        """Search retrieval documents for a branch."""

        if self.session.bind is None:
            raise ValueError("session is not bound")
        dialect = self.session.bind.dialect.name
        if dialect == "postgresql":
            config_name = self._fts_config_name()
            sql = text(
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
            rows = self.session.execute(
                sql,
                {"branch_id": branch_id, "query": query, "limit": limit},
            ).mappings().all()
            if rows:
                return [self._row_to_hit(row) for row in rows]

            fallback_rows = self.session.execute(
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
                {"branch_id": branch_id, "query": query, "limit": limit},
            ).mappings().all()
            if fallback_rows:
                return [self._row_to_hit(row) for row in fallback_rows]

            tokens = [token.strip() for token in query.split() if token.strip()]
            if not tokens:
                tokens = [query]
            clauses = []
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
                  AND ({' OR '.join(clauses)})
                ORDER BY chapter_index ASC
                LIMIT :limit
                """
            )
            like_rows = self.session.execute(sql_like, params).mappings().all()
            if like_rows:
                return [self._row_to_hit(row) for row in like_rows]
            return self._keyword_overlap_fallback(branch_id, query, limit)

        raise RuntimeError(
            "Only PostgreSQL is supported for retrieval search; "
            "SQLite fallback has been removed."
        )
