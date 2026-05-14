"""Context assembly for chapter-by-chapter deconstruction.

Supports two modes:
- Legacy fixed-window: top-N facts by recency (backward compatible)
- Adaptive: query-aware retrieval driven by intake entities/events
"""

from __future__ import annotations

import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ChapterArtifact, FactRecord, GraphNode, WindowArtifact
from novel_analyzer.services.arc_memory_service import ArcMemoryService
from novel_analyzer.services.entity_resolution_service import EntityResolutionService
from novel_analyzer.services.foreshadowing_service import ForeshadowingService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.run_service import default_readable_artifact_clause


class ContextService:
    """Build prior context payloads for later chapter analysis."""

    ADAPTIVE_FACT_LIMIT = 30
    ADAPTIVE_RELEVANT_LIMIT = 16
    ADAPTIVE_RECENCY_LIMIT = 8
    ADAPTIVE_FORESHADOW_LIMIT = 6

    def __init__(self, session: Session) -> None:
        self.session = session

    def previous_summary(self, branch_id: str, chapter_index: int) -> str:
        """Return the latest prior chapter summary, if any."""

        if chapter_index <= 1:
            return ''
        artifact = self.session.scalar(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.chapter_index == chapter_index - 1)
            .where(default_readable_artifact_clause())
        )
        if artifact is None:
            return ''
        return str(artifact.payload_json.get('chapter_summary', ''))

    def fact_context_json(
        self,
        branch_id: str,
        chapter_index: int,
        limit: int = 20,
    ) -> dict[str, object]:
        """Return a compact fact context snapshot from earlier chapters."""

        rows = self.session.scalars(
            select(FactRecord)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index < chapter_index)
            .order_by(FactRecord.chapter_index.desc(), FactRecord.created_at.desc())
            .limit(limit)
        ).all()
        facts = [
            {
                'chapter_index': row.chapter_index,
                'fact_type': row.fact_type,
                'label': row.label,
                'confidence': row.confidence,
            }
            for row in reversed(rows)
        ]
        return {'facts': facts}

    def _expand_queries_from_graph(
        self,
        branch_id: str,
        chapter_index: int,
        query_entities: list[str],
        max_expansion: int = 6,
    ) -> list[str]:
        """Expand query terms using 1-hop graph neighbors for better recall."""
        if not query_entities:
            return []
        from novel_analyzer.database.models import GraphEdge, GraphNode
        entity_nodes = self.session.scalars(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.label.in_(query_entities))
            .where(GraphNode.chapter_first_seen < chapter_index)
        ).all()
        if not entity_nodes:
            return []
        node_ids = [n.id for n in entity_nodes]
        neighbor_edges = self.session.scalars(
            select(GraphEdge)
            .where(GraphEdge.branch_id == branch_id)
            .where(
                GraphEdge.source_node_id.in_(node_ids)
                | GraphEdge.target_node_id.in_(node_ids)
            )
            .order_by(GraphEdge.weight.desc())
            .limit(max_expansion * 2)
        ).all()
        neighbor_ids: set[str] = set()
        for edge in neighbor_edges:
            if edge.source_node_id not in node_ids:
                neighbor_ids.add(edge.source_node_id)
            if edge.target_node_id not in node_ids:
                neighbor_ids.add(edge.target_node_id)
        if not neighbor_ids:
            return []
        neighbors = self.session.scalars(
            select(GraphNode)
            .where(GraphNode.id.in_(list(neighbor_ids)[:max_expansion]))
        ).all()
        existing = {q.lower() for q in query_entities}
        return [
            n.label for n in neighbors
            if n.label.lower() not in existing and len(n.label) >= 2
        ][:max_expansion]

    @staticmethod
    def _label_matches(label: str, queries: set[str]) -> float:
        """Score how well a fact label matches the query entities/events."""
        if not queries or not label:
            return 0.0
        label_lower = label.lower()
        score = 0.0
        for query in queries:
            if query in label_lower:
                score += 1.0
            elif len(query) >= 2 and any(
                query[i:i+2] in label_lower for i in range(len(query) - 1)
            ):
                score += 0.3
        return score

    def adaptive_fact_context_json(
        self,
        branch_id: str,
        chapter_index: int,
        query_entities: list[str],
        query_events: list[str],
    ) -> dict[str, object]:
        """Query-aware fact retrieval: prioritize facts relevant to current chapter entities.

        Combines three retrieval strategies:
        1. Relevance-ranked: facts whose labels match current chapter entities/events
        2. Recency: most recent facts (preserves continuity)
        3. Foreshadowing: open foreshadowing facts that may be paid off
        """
        if chapter_index <= 1:
            return {'facts': [], 'retrieval_mode': 'adaptive', 'query_terms': []}

        er = EntityResolutionService(self.session)
        resolved_entities = [
            er.resolve_canonical(branch_id, e) for e in query_entities
        ]
        all_query_terms = list(set(query_entities + resolved_entities))

        graph_expanded = self._expand_queries_from_graph(branch_id, chapter_index, all_query_terms)
        all_query_terms = list(set(all_query_terms + graph_expanded))

        queries = {
            q.strip().lower()
            for q in (all_query_terms + query_events)
            if q.strip()
        }

        all_prior_facts = self.session.scalars(
            select(FactRecord)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index < chapter_index)
            .order_by(FactRecord.chapter_index.desc(), FactRecord.created_at.desc())
            .limit(self.ADAPTIVE_FACT_LIMIT * 3)
        ).all()

        if not all_prior_facts:
            return {'facts': [], 'retrieval_mode': 'adaptive', 'query_terms': list(queries)}

        scored: list[tuple[float, FactRecord]] = []
        for row in all_prior_facts:
            relevance = self._label_matches(row.label, queries)
            if relevance > 0:
                scored.append((relevance, row))
        scored.sort(key=lambda x: (-x[0], -x[1].chapter_index))
        relevant_facts = [row for _, row in scored[:self.ADAPTIVE_RELEVANT_LIMIT]]

        relevant_ids = {id(r) for r in relevant_facts}
        recency_facts = [
            row for row in all_prior_facts
            if id(row) not in relevant_ids
        ][:self.ADAPTIVE_RECENCY_LIMIT]

        foreshadow_facts = self.session.scalars(
            select(FactRecord)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index < chapter_index)
            .where(FactRecord.fact_type == 'foreshadowing')
            .order_by(FactRecord.chapter_index.asc())
            .limit(self.ADAPTIVE_FORESHADOW_LIMIT)
        ).all()
        existing_ids = relevant_ids | {id(r) for r in recency_facts}
        foreshadow_unique = [r for r in foreshadow_facts if id(r) not in existing_ids]

        merged: list[FactRecord] = []
        seen_labels: set[str] = set()
        for row in relevant_facts + foreshadow_unique + recency_facts:
            key = f"{row.chapter_index}:{row.label}"
            if key not in seen_labels:
                seen_labels.add(key)
                merged.append(row)

        merged.sort(key=lambda r: (r.chapter_index, r.fact_type))

        facts = [
            {
                'chapter_index': row.chapter_index,
                'fact_type': row.fact_type,
                'label': row.label,
                'confidence': row.confidence,
                'relevance': 'query_match' if id(row) in relevant_ids else 'recency',
            }
            for row in merged[:self.ADAPTIVE_FACT_LIMIT]
        ]
        return {
            'facts': facts,
            'retrieval_mode': 'adaptive',
            'query_terms': list(queries)[:10],
            'relevant_count': len(relevant_facts),
            'recency_count': len(recency_facts),
            'foreshadow_count': len(foreshadow_unique),
            'open_foreshadowing_threads': ForeshadowingService(
                self.session
            ).open_threads_context_json(branch_id, chapter_index, limit=8),
            'arc_memory': ArcMemoryService(
                self.session
            ).build_tiered_context(branch_id, chapter_index),
        }

    def adaptive_graph_context_json(
        self,
        branch_id: str,
        chapter_index: int,
        query_entities: list[str],
        node_limit: int = 16,
        edge_limit: int = 16,
    ) -> dict[str, object]:
        """Query-aware graph context: prioritize nodes related to current chapter entities."""

        if chapter_index <= 1:
            return {
                'overview': {'node_count': 0, 'edge_count': 0, 'node_type_counts': {}, 'edge_type_counts': {}},
                'central_nodes': [],
                'recent_timeline': [],
                'reasoning_paths': [],
                'active_conflicts': [],
                'open_foreshadowing': [],
                'world_rules': [],
                'nodes': [],
                'edges': [],
                'retrieval_mode': 'adaptive',
            }

        snapshot = GraphService(self.session).reasoning_snapshot(
            branch_id,
            upto_chapter=chapter_index - 1,
            node_limit=node_limit * 2,
            edge_limit=edge_limit * 2,
        )

        if not query_entities:
            snapshot['nodes'] = snapshot.get('nodes', [])[:node_limit]
            snapshot['edges'] = snapshot.get('edges', [])[:edge_limit]
            return snapshot

        queries = {q.strip().lower() for q in query_entities if q.strip()}
        nodes = snapshot.get('nodes', [])

        scored_nodes: list[tuple[float, dict]] = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            label = str(node.get('label', '')).lower()
            score = self._label_matches(label, queries)
            # Boost open foreshadowing and active conflicts
            status = str(node.get('status', ''))
            if status in ('open', 'active', 'escalated'):
                score += 0.5
            scored_nodes.append((score, node))

        scored_nodes.sort(key=lambda x: (-x[0], str(x[1].get('label', ''))))
        snapshot['nodes'] = [n for _, n in scored_nodes[:node_limit]]

        retained_labels = {str(n.get('label', '')) for n in snapshot['nodes']}
        edges = snapshot.get('edges', [])
        relevant_edges = [
            e for e in edges
            if isinstance(e, dict) and (
                str(e.get('source', '')) in retained_labels
                or str(e.get('target', '')) in retained_labels
            )
        ][:edge_limit]
        snapshot['edges'] = relevant_edges
        snapshot['retrieval_mode'] = 'adaptive'

        return snapshot

    def graph_context_json(
        self,
        branch_id: str,
        chapter_index: int,
        node_limit: int = 12,
        edge_limit: int = 12,
    ) -> dict[str, object]:
        """Return a reasoning-oriented graph snapshot from earlier chapters."""

        if chapter_index <= 1:
            return {
                'overview': {
                    'node_count': 0,
                    'edge_count': 0,
                    'node_type_counts': {},
                    'edge_type_counts': {},
                },
                'central_nodes': [],
                'recent_timeline': [],
                'reasoning_paths': [],
                'active_conflicts': [],
                'open_foreshadowing': [],
                'world_rules': [],
                'nodes': [],
                'edges': [],
            }
        return GraphService(self.session).reasoning_snapshot(
            branch_id,
            upto_chapter=chapter_index - 1,
            node_limit=node_limit,
            edge_limit=edge_limit,
        )

    def state_summary_json(self, branch_id: str, chapter_index: int) -> dict[str, object]:
        """Return prior state-summary context from the reasoning graph."""

        if chapter_index <= 1:
            return {
                'new_foreshadowing': [],
                'paid_off_foreshadowing': [],
                'new_conflicts': [],
                'escalated_conflicts': [],
                'stable_relations': [],
                'evolved_relations': [],
                'observed_world_rules': [],
                'constraining_world_rules': [],
            }
        snapshot = GraphService(self.session).reasoning_snapshot(
            branch_id,
            upto_chapter=chapter_index - 1,
            node_limit=12,
            edge_limit=12,
        )
        return GraphService.state_summary_from_snapshot(
            snapshot,
            chapter_index=chapter_index - 1,
        )

    def window_summary(self, branch_id: str, chapter_index: int) -> str:
        """Return the latest completed window summary before this chapter."""

        if chapter_index <= 1:
            return ''
        window = self.session.scalar(
            select(WindowArtifact)
            .where(WindowArtifact.branch_id == branch_id)
            .where(WindowArtifact.window_end_chapter < chapter_index)
            .order_by(WindowArtifact.window_end_chapter.desc())
        )
        if window is None:
            return ''
        return str(window.payload_json.get('window_summary', ''))

    def context_bundle(
        self,
        branch_id: str,
        chapter_index: int,
        fact_limit: int = 20,
    ) -> dict[str, object]:
        """Return the assembled prior context that later chapters will consume."""

        return {
            'chapter_index': chapter_index,
            'previous_summary': self.previous_summary(branch_id, chapter_index),
            'fact_context': self.fact_context_json(branch_id, chapter_index, fact_limit),
            'graph_context': self.graph_context_json(branch_id, chapter_index),
            'state_summary': self.state_summary_json(branch_id, chapter_index),
            'window_summary': self.window_summary(branch_id, chapter_index),
        }
