"""Retrieval benchmark: compare FTS config impact on recall and MRR.

Measures the net gain of jieba-tokenized query (jiebacfg) vs simple tokenization
against the same bm25_vector column (which is already jieba-indexed).

Ground truth: each chapter's own query_hints are used as queries; the correct
answer is that chapter_index. No manual annotation required.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings, get_settings


@dataclass
class QueryResult:
    query: str
    relevant_chapter: int
    ranked_chapters: list[int]
    latency_ms: float

    def hit_at_k(self, k: int) -> bool:
        return self.relevant_chapter in self.ranked_chapters[:k]

    def reciprocal_rank(self) -> float:
        try:
            rank = self.ranked_chapters.index(self.relevant_chapter) + 1
            return 1.0 / rank
        except ValueError:
            return 0.0


@dataclass
class ConfigResult:
    config_name: str
    query_results: list[QueryResult] = field(default_factory=list)

    def recall_at_k(self, k: int) -> float:
        if not self.query_results:
            return 0.0
        return sum(1 for r in self.query_results if r.hit_at_k(k)) / len(self.query_results)

    def mrr(self) -> float:
        if not self.query_results:
            return 0.0
        return sum(r.reciprocal_rank() for r in self.query_results) / len(self.query_results)

    def avg_latency_ms(self) -> float:
        if not self.query_results:
            return 0.0
        return sum(r.latency_ms for r in self.query_results) / len(self.query_results)

    def to_dict(self, k_values: list[int]) -> dict[str, Any]:
        return {
            "config": self.config_name,
            "query_count": len(self.query_results),
            "mrr": round(self.mrr(), 4),
            **{f"recall@{k}": round(self.recall_at_k(k), 4) for k in k_values},
            "avg_latency_ms": round(self.avg_latency_ms(), 2),
        }


@dataclass
class RetrievalBenchmarkReport:
    branch_id: str
    total_docs: int
    queries_used: int
    elapsed_seconds: float
    configs: list[ConfigResult] = field(default_factory=list)
    k_values: list[int] = field(default_factory=lambda: [1, 3, 5])

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": "retrieval-benchmark.v2",
            "branch_id": self.branch_id,
            "total_docs": self.total_docs,
            "queries_used": self.queries_used,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "k_values": self.k_values,
            "results": [c.to_dict(self.k_values) for c in self.configs],
            "delta": self._delta_dict(),
        }

    def _delta_dict(self) -> dict[str, Any]:
        if len(self.configs) < 2:
            return {}
        base = self.configs[0]
        comp = self.configs[1]
        delta: dict[str, Any] = {
            "mrr": round(comp.mrr() - base.mrr(), 4),
            "avg_latency_ms": round(comp.avg_latency_ms() - base.avg_latency_ms(), 2),
        }
        for k in self.k_values:
            delta[f"recall@{k}"] = round(comp.recall_at_k(k) - base.recall_at_k(k), 4)
        return delta


class RetrievalBenchmarkService:
    DEFAULT_K_VALUES = [1, 3, 5]
    DEFAULT_FETCH_LIMIT = 10

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    def run(
        self,
        branch_id: str,
        configs: list[str] | None = None,
        max_queries: int | None = None,
        k_values: list[int] | None = None,
    ) -> RetrievalBenchmarkReport:
        k_vals = k_values or self.DEFAULT_K_VALUES
        fetch_limit = max(k_vals) * 2

        available_configs = self._available_configs()
        if configs is None:
            configs = [c for c in ["simple", "jiebacfg"] if c in available_configs]
        else:
            configs = [c for c in configs if c in available_configs]

        query_bank = self._build_query_bank(branch_id, max_queries)
        total_docs = self._count_docs(branch_id)
        started_at = time.perf_counter()

        config_results: list[ConfigResult] = []
        for cfg in configs:
            cr = ConfigResult(config_name=cfg)
            for relevant_chapter, query in query_bank:
                t0 = time.perf_counter()
                ranked = self._fts_search(branch_id, query, cfg, fetch_limit)
                latency_ms = (time.perf_counter() - t0) * 1000
                cr.query_results.append(
                    QueryResult(
                        query=query,
                        relevant_chapter=relevant_chapter,
                        ranked_chapters=ranked,
                        latency_ms=latency_ms,
                    )
                )
            config_results.append(cr)

        return RetrievalBenchmarkReport(
            branch_id=branch_id,
            total_docs=total_docs,
            queries_used=len(query_bank),
            elapsed_seconds=time.perf_counter() - started_at,
            configs=config_results,
            k_values=k_vals,
        )

    def _available_configs(self) -> set[str]:
        rows = self.session.execute(
            text(
                "SELECT cfgname FROM pg_ts_config "
                "WHERE cfgname IN ('jiebacfg','jiebaqry','simple')"
            )
        ).all()
        return {r[0] for r in rows}

    def _count_docs(self, branch_id: str) -> int:
        row = self.session.execute(
            text("SELECT COUNT(*) FROM retrieval_documents WHERE branch_id = :bid"),
            {"bid": branch_id},
        ).scalar()
        return int(row or 0)

    def _build_query_bank(
        self, branch_id: str, max_queries: int | None
    ) -> list[tuple[int, str]]:
        rows = self.session.execute(
            text(
                "SELECT chapter_index, keyword_list FROM retrieval_documents "
                "WHERE branch_id = :bid ORDER BY chapter_index"
            ),
            {"bid": branch_id},
        ).all()

        term_doc_freq: dict[str, int] = {}
        chapter_terms: list[tuple[int, list[str]]] = []
        for chapter_index, keywords in rows:
            if not keywords:
                continue
            short_kws = [
                k.strip() for k in keywords
                if k and 2 <= len(k.strip()) <= 10
                and "。" not in k and " " not in k
            ]
            chapter_terms.append((chapter_index, short_kws))
            for kw in set(short_kws):
                term_doc_freq[kw] = term_doc_freq.get(kw, 0) + 1

        total_chapters = len(chapter_terms) or 1
        max_df_ratio = 0.4

        bank: list[tuple[int, str]] = []
        for chapter_index, kws in chapter_terms:
            discriminative = [
                k for k in kws
                if term_doc_freq.get(k, 0) / total_chapters <= max_df_ratio
            ]
            chosen = discriminative[:3] if len(discriminative) >= 2 else (kws[:3] if kws else [])
            if not chosen:
                continue
            bank.append((chapter_index, " ".join(chosen)))
            if max_queries and len(bank) >= max_queries:
                break
        return bank

    def _fts_search(
        self, branch_id: str, query: str, config: str, limit: int
    ) -> list[int]:
        terms = [t.strip() for t in query.split() if t.strip()]
        if not terms:
            return []
        tsquery_expr = " && ".join(
            f"plainto_tsquery('{config}'::regconfig, {repr(t)})" for t in terms
        )
        sql = text(
            f"""
            SELECT chapter_index
            FROM retrieval_documents
            WHERE branch_id = :bid
              AND bm25_vector @@ ({tsquery_expr})
            ORDER BY ts_rank_cd(bm25_vector, {tsquery_expr}) DESC
            LIMIT :limit
            """
        )
        rows = self.session.execute(sql, {"bid": branch_id, "limit": limit}).all()
        return [r[0] for r in rows]

    @staticmethod
    def _tsvector_terms(vec_text: str) -> set[str]:
        import re
        return set(re.findall(r"'((?:[^']|'')+)'", vec_text))
