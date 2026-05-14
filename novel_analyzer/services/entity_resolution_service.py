"""Entity resolution: merge co-referent labels across chapters.

Detects when different labels refer to the same entity (e.g. "卫图" = "那个少年")
and maintains a canonical alias map. This improves graph quality, adaptive retrieval
precision, and foreshadowing lifecycle accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from novel_analyzer.database.models import FactRecord, GraphNode


@dataclass(frozen=True, slots=True)
class AliasCluster:
    canonical: str
    aliases: frozenset[str]
    confidence: float


class EntityResolutionService:
    """Merges co-referent entity labels within a branch."""

    SIMILARITY_THRESHOLD = 0.6
    MIN_LABEL_LENGTH = 2

    _branch_cache: dict[str, dict[str, str]] = {}
    _branch_cache_version: dict[str, int] = {}

    def __init__(self, session: Session) -> None:
        self.session = session
        self._alias_cache: dict[str, str] = {}

    def resolve_canonical(self, branch_id: str, label: str) -> str:
        """Return the canonical label for a given alias, or the label itself."""
        cached_map = self._branch_cache.get(branch_id)
        if cached_map and label in cached_map:
            return cached_map[label]
        if label in self._alias_cache:
            return self._alias_cache[label]
        node = self.session.scalar(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.node_type == 'character')
            .where(GraphNode.label == label)
        )
        if node is None:
            return label
        canonical = (node.metadata_json or {}).get('canonical_label', label)
        self._alias_cache[label] = str(canonical)
        return str(canonical)

    def build_alias_map(self, branch_id: str) -> dict[str, str]:
        """Build a complete alias -> canonical mapping for all character nodes."""
        node_count = self.session.scalar(
            select(func.count(GraphNode.id))
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.node_type == 'character')
        ) or 0
        cached_version = self._branch_cache_version.get(branch_id, -1)
        if cached_version == node_count and branch_id in self._branch_cache:
            return self._branch_cache[branch_id]

        nodes = self.session.scalars(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.node_type == 'character')
            .order_by(GraphNode.occurrence_count.desc())
        ).all()

        clusters: list[list[GraphNode]] = []
        assigned: set[str] = set()

        for node in nodes:
            if node.id in assigned:
                continue
            cluster = [node]
            assigned.add(node.id)
            for candidate in nodes:
                if candidate.id in assigned:
                    continue
                if self._should_merge(node.label, candidate.label):
                    cluster.append(candidate)
                    assigned.add(candidate.id)
            if len(cluster) > 1:
                clusters.append(cluster)

        alias_map: dict[str, str] = {}
        for cluster in clusters:
            canonical = max(cluster, key=lambda n: (n.occurrence_count, -len(n.label)))
            for node in cluster:
                if node.id != canonical.id:
                    alias_map[node.label] = canonical.label
                    meta = dict(node.metadata_json or {})
                    meta['canonical_label'] = canonical.label
                    meta['is_alias'] = True
                    node.metadata_json = meta
            canonical_meta = dict(canonical.metadata_json or {})
            canonical_meta['canonical_label'] = canonical.label
            canonical_meta['aliases'] = [n.label for n in cluster if n.id != canonical.id]
            canonical.metadata_json = canonical_meta

        self._alias_cache = alias_map
        self._branch_cache[branch_id] = alias_map
        self._branch_cache_version[branch_id] = node_count
        return alias_map

    def merge_fact_labels(
        self,
        branch_id: str,
        chapter_index: int,
        facts_data: dict[str, object],
    ) -> dict[str, object]:
        """Apply entity resolution to fact extraction output, merging aliases."""
        if not self._alias_cache:
            self.build_alias_map(branch_id)

        if not self._alias_cache:
            return facts_data

        merged = dict(facts_data)
        for key in ('characters', 'events', 'relations', 'conflicts', 'foreshadowing'):
            items = merged.get(key, [])
            if not isinstance(items, list):
                continue
            resolved_items = []
            for item in items:
                if isinstance(item, dict):
                    label = str(item.get('label', ''))
                    canonical = self._alias_cache.get(label, label)
                    if canonical != label:
                        item = dict(item)
                        item['label'] = canonical
                        item.setdefault('original_label', label)
                    resolved_items.append(item)
                else:
                    resolved_items.append(item)
            merged[key] = resolved_items
        return merged

    @classmethod
    def _should_merge(cls, label_a: str, label_b: str) -> bool:
        """Determine if two labels likely refer to the same entity."""
        a = label_a.strip()
        b = label_b.strip()
        if len(a) < cls.MIN_LABEL_LENGTH or len(b) < cls.MIN_LABEL_LENGTH:
            return False
        if a == b:
            return True
        if a in b or b in a:
            return len(min(a, b, key=len)) >= 2
        sim = cls._char_similarity(a, b)
        return sim >= cls.SIMILARITY_THRESHOLD

    @staticmethod
    def _char_similarity(a: str, b: str) -> float:
        """Character-level Jaccard similarity for Chinese text."""
        if not a or not b:
            return 0.0
        set_a = set(a)
        set_b = set(b)
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        if union == 0:
            return 0.0
        return intersection / union
