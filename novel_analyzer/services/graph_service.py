"""Reasoning-graph materialization from chapter artifacts and staged fact records."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ChapterArtifact, ChapterRawOutput, GraphEdge, GraphNode


@dataclass(frozen=True, slots=True)
class GraphSummary:
    """Human-usable summary of a branch reasoning graph."""

    branch_id: str
    node_count: int
    edge_count: int
    node_type_counts: dict[str, int]
    edge_type_counts: dict[str, int]
    top_entities: list[tuple[str, int]]
    top_events: list[tuple[str, int]]
    top_conflicts: list[tuple[str, int]]
    progression_edges: list[str]
    reasoning_paths: list[str]
    open_foreshadowing: list[str]
    active_conflicts: list[str]
    world_rules: list[str]


class GraphService:
    """Build a richer narrative reasoning graph for one branch."""

    _TRACKED_STAGE_KEYS = (
        'characters',
        'events',
        'relations',
        'conflicts',
        'foreshadowing',
        'worldbuilding_facts',
    )

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _normalize_label(label: str) -> str:
        return re.sub(r'\s+', ' ', label.strip())

    @staticmethod
    def state_summary_from_snapshot(
        snapshot: dict[str, object],
        *,
        chapter_index: int | None = None,
    ) -> dict[str, object]:
        """Derive human-usable state summary slices from a reasoning snapshot."""

        state_machine = snapshot.get('state_machine', {})
        if not isinstance(state_machine, dict):
            state_machine = {}

        def _entries(key: str) -> list[dict[str, object]]:
            raw = state_machine.get(key, [])
            if not isinstance(raw, list):
                return []
            return [item for item in raw if isinstance(item, dict)]

        def _labels(
            key: str,
            status: str | None = None,
            *,
            chapter_exact: int | None = None,
        ) -> list[str]:
            labels: list[str] = []
            for item in _entries(key):
                if status is not None and item.get('status') != status:
                    continue
                if chapter_exact is not None and item.get('chapter_first_seen') != chapter_exact:
                    continue
                label = str(item.get('label', '')).strip()
                if label:
                    labels.append(label)
            return labels

        chapter_exact = chapter_index
        return {
            'new_foreshadowing': _labels('foreshadow', 'open', chapter_exact=chapter_exact),
            'paid_off_foreshadowing': _labels('foreshadow', 'paid_off'),
            'new_conflicts': _labels('conflict', 'active', chapter_exact=chapter_exact),
            'escalated_conflicts': _labels('conflict', 'escalated'),
            'stable_relations': _labels('relation', 'stable'),
            'evolved_relations': _labels('relation', 'evolved'),
            'observed_world_rules': _labels('world_rule', 'observed'),
            'constraining_world_rules': _labels('world_rule', 'constraining'),
        }

    @classmethod
    def _compact_label(cls, label: str) -> str:
        return re.sub(r'[\W_]+', '', cls._normalize_label(label), flags=re.UNICODE)

    @classmethod
    def _bi_grams(cls, label: str) -> set[str]:
        compact = cls._compact_label(label)
        if len(compact) < 2:
            return {compact} if compact else set()
        return {compact[index : index + 2] for index in range(len(compact) - 1)}

    @classmethod
    def _labels_related(cls, left: str, right: str) -> bool:
        left_compact = cls._compact_label(left)
        right_compact = cls._compact_label(right)
        if not left_compact or not right_compact:
            return False
        if left_compact in right_compact or right_compact in left_compact:
            return min(len(left_compact), len(right_compact)) >= 2
        return bool(cls._bi_grams(left_compact) & cls._bi_grams(right_compact))

    @staticmethod
    def _merge_metadata(
        original: dict[str, object] | None,
        incoming: dict[str, object] | None,
    ) -> dict[str, object]:
        merged: dict[str, object] = dict(original or {})
        for key, value in (incoming or {}).items():
            if value in (None, '', [], {}):
                continue
            existing = merged.get(key)
            if isinstance(existing, list) and isinstance(value, list):
                seen = {json.dumps(item, ensure_ascii=False, sort_keys=True) for item in existing}
                for item in value:
                    marker = json.dumps(item, ensure_ascii=False, sort_keys=True)
                    if marker not in seen:
                        existing.append(item)
                        seen.add(marker)
                merged[key] = existing
                continue
            if isinstance(existing, dict) and isinstance(value, dict):
                merged[key] = {**existing, **value}
                continue
            merged[key] = value
        return merged

    def _upsert_node(
        self,
        cache: dict[tuple[str, str], GraphNode],
        branch_id: str,
        node_type: str,
        label: str,
        chapter_index: int,
        metadata_json: dict[str, object] | None = None,
    ) -> GraphNode:
        normalized_label = self._normalize_label(label)
        key = (node_type, normalized_label)
        node = cache.get(key)
        if node is None:
            node = GraphNode(
                branch_id=branch_id,
                node_type=node_type,
                label=normalized_label,
                chapter_first_seen=chapter_index,
                chapter_last_seen=chapter_index,
                occurrence_count=1,
                metadata_json=metadata_json or {},
            )
            self.session.add(node)
            self.session.flush([node])
            cache[key] = node
            return node
        node.chapter_last_seen = chapter_index
        node.occurrence_count += 1
        node.metadata_json = self._merge_metadata(node.metadata_json, metadata_json)
        return node

    def _upsert_edge(
        self,
        cache: dict[tuple[str, str, str], GraphEdge],
        branch_id: str,
        source_node: GraphNode,
        target_node: GraphNode,
        edge_type: str,
        chapter_index: int,
        metadata_json: dict[str, object] | None = None,
        weight_increment: float = 1.0,
    ) -> GraphEdge:
        key = (source_node.id, target_node.id, edge_type)
        edge = cache.get(key)
        if edge is None:
            edge = GraphEdge(
                branch_id=branch_id,
                source_node_id=source_node.id,
                target_node_id=target_node.id,
                edge_type=edge_type,
                weight=weight_increment,
                chapter_first_seen=chapter_index,
                chapter_last_seen=chapter_index,
                metadata_json=metadata_json or {},
            )
            self.session.add(edge)
            self.session.flush([edge])
            cache[key] = edge
            return edge
        edge.chapter_last_seen = chapter_index
        edge.weight += weight_increment
        edge.metadata_json = self._merge_metadata(edge.metadata_json, metadata_json)
        return edge

    @staticmethod
    def _normalize_note_list(raw: object) -> list[dict[str, object]]:
        if not isinstance(raw, list):
            return []
        normalized: list[dict[str, object]] = []
        for item in raw:
            if isinstance(item, str):
                label = item.strip()
                if label:
                    normalized.append({'label': label, 'evidence': [label], 'confidence': 0.5})
                continue
            if not isinstance(item, dict):
                continue
            label_obj = (
                item.get('label')
                or item.get('name')
                or item.get('title')
                or item.get('summary')
            )
            label_text = str(label_obj or '').strip()
            if not label_text:
                continue
            evidence = item.get('evidence', [])
            normalized.append(
                {
                    'label': label_text,
                    'evidence': evidence if isinstance(evidence, list) else [str(evidence)],
                    'confidence': float(item.get('confidence', 0.5) or 0.5),
                }
            )
        return normalized

    def _latest_stage_payload(self, branch_id: str, chapter_index: int) -> dict[str, object]:
        raw_output = self.session.scalar(
            select(ChapterRawOutput)
            .where(ChapterRawOutput.branch_id == branch_id)
            .where(ChapterRawOutput.chapter_index == chapter_index)
            .where(ChapterRawOutput.parse_status == 'parsed')
            .order_by(ChapterRawOutput.job_attempt.desc(), ChapterRawOutput.created_at.desc())
        )
        if raw_output is None:
            return {}
        raw_text = raw_output.raw_response_text.strip()
        if not raw_text:
            return {}
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _chapter_reasoning_inputs(
        self,
        artifact: ChapterArtifact,
    ) -> dict[str, list[dict[str, object]]]:
        payload = artifact.payload_json
        stage_payload = self._latest_stage_payload(artifact.branch_id, artifact.chapter_index)
        facts_payload = stage_payload.get('facts', {})
        analysis_payload = stage_payload.get('analysis', {})

        if not isinstance(facts_payload, dict):
            facts_payload = {}
        if not isinstance(analysis_payload, dict):
            analysis_payload = {}

        entity_items = self._normalize_note_list(facts_payload.get('characters', []))
        if not entity_items:
            entity_items = self._normalize_note_list(payload.get('key_entities', []))

        event_items = self._normalize_note_list(facts_payload.get('events', []))
        if not event_items:
            event_items = self._normalize_note_list(payload.get('key_events', []))

        continuity_raw = analysis_payload.get(
            'continuity_notes',
            payload.get('continuity_notes', []),
        )
        continuity_items = self._normalize_note_list(continuity_raw)

        return {
            'entities': entity_items,
            'events': event_items,
            'relations': self._normalize_note_list(facts_payload.get('relations', [])),
            'conflicts': self._normalize_note_list(facts_payload.get('conflicts', [])),
            'foreshadowing': self._normalize_note_list(facts_payload.get('foreshadowing', [])),
            'world_rules': self._normalize_note_list(facts_payload.get('worldbuilding_facts', [])),
            'continuity': continuity_items,
        }

    def _matching_nodes(
        self,
        nodes: list[GraphNode],
        label: str,
        *,
        allowed_types: set[str] | None = None,
    ) -> list[GraphNode]:
        matches: list[GraphNode] = []
        seen: set[str] = set()
        for node in nodes:
            if allowed_types is not None and node.node_type not in allowed_types:
                continue
            if node.id in seen:
                continue
            if self._labels_related(node.label, label):
                matches.append(node)
                seen.add(node.id)
        return matches

    def _apply_secondary_node_links(
        self,
        branch_id: str,
        chapter_index: int,
        edge_cache: dict[tuple[str, str, str], GraphEdge],
        current_nodes: list[GraphNode],
        prior_nodes: list[GraphNode],
        source_nodes: list[GraphNode],
        target_types: set[str],
        edge_type: str,
        *,
        reverse_edge_type: str | None = None,
    ) -> None:
        candidate_nodes = current_nodes + prior_nodes
        for source in source_nodes:
            matches = self._matching_nodes(
                candidate_nodes,
                source.label,
                allowed_types=target_types,
            )
            for target in matches:
                if target.id == source.id:
                    continue
                self._upsert_edge(
                    edge_cache,
                    branch_id,
                    source,
                    target,
                    edge_type,
                    chapter_index,
                    metadata_json={'provenance': 'heuristic-label-match'},
                )
                if reverse_edge_type is not None:
                    self._upsert_edge(
                        edge_cache,
                        branch_id,
                        target,
                        source,
                        reverse_edge_type,
                        chapter_index,
                        metadata_json={'provenance': 'heuristic-label-match'},
                    )

    def _rebuild_branch_graph(self, branch_id: str) -> tuple[list[GraphNode], list[GraphEdge]]:
        self.session.execute(delete(GraphEdge).where(GraphEdge.branch_id == branch_id))
        self.session.flush()
        self.session.execute(delete(GraphNode).where(GraphNode.branch_id == branch_id))
        self.session.flush()

        artifacts = self.session.scalars(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.visibility == 'active')
            .where(ChapterArtifact.participates_in_downstream.is_(True))
            .order_by(ChapterArtifact.chapter_index, ChapterArtifact.created_at)
        ).all()

        node_cache: dict[tuple[str, str], GraphNode] = {}
        edge_cache: dict[tuple[str, str, str], GraphEdge] = {}
        prior_event_nodes: list[GraphNode] = []
        prior_conflict_nodes: list[GraphNode] = []
        prior_relation_nodes: list[GraphNode] = []
        prior_foreshadow_nodes: list[GraphNode] = []
        prior_nodes: list[GraphNode] = []

        for artifact in artifacts:
            chapter_index = artifact.chapter_index
            chapter_inputs = self._chapter_reasoning_inputs(artifact)

            current_nodes: list[GraphNode] = []
            entity_nodes: list[GraphNode] = []
            event_nodes: list[GraphNode] = []
            relation_nodes: list[GraphNode] = []
            conflict_nodes: list[GraphNode] = []
            foreshadow_nodes: list[GraphNode] = []
            world_rule_nodes: list[GraphNode] = []
            continuity_nodes: list[GraphNode] = []

            for item in chapter_inputs['entities']:
                node = self._upsert_node(
                    node_cache,
                    branch_id,
                    'entity',
                    str(item['label']),
                    chapter_index,
                    metadata_json={
                        'confidence': item.get('confidence', 0.5),
                        'evidence': item.get('evidence', []),
                    },
                )
                entity_nodes.append(node)
                current_nodes.append(node)

            for item in chapter_inputs['events']:
                node = self._upsert_node(
                    node_cache,
                    branch_id,
                    'event',
                    str(item['label']),
                    chapter_index,
                    metadata_json={
                        'confidence': item.get('confidence', 0.5),
                        'evidence': item.get('evidence', []),
                    },
                )
                event_nodes.append(node)
                current_nodes.append(node)

            node_groups = [
                ('relation', 'relations', relation_nodes),
                ('conflict', 'conflicts', conflict_nodes),
                ('foreshadow', 'foreshadowing', foreshadow_nodes),
                ('world_rule', 'world_rules', world_rule_nodes),
                ('continuity', 'continuity', continuity_nodes),
            ]
            for node_type, input_key, target in node_groups:
                for item in chapter_inputs[input_key]:
                    node = self._upsert_node(
                        node_cache,
                        branch_id,
                        node_type,
                        str(item['label']),
                        chapter_index,
                        metadata_json={
                            'confidence': item.get('confidence', 0.5),
                            'evidence': item.get('evidence', []),
                        },
                    )
                    target.append(node)
                    current_nodes.append(node)

            for left, right in combinations(entity_nodes, 2):
                self._upsert_edge(
                    edge_cache,
                    branch_id,
                    left,
                    right,
                    'co_occurs',
                    chapter_index,
                    metadata_json={'provenance': 'same-chapter'},
                )

            previous_event = prior_event_nodes[-1] if prior_event_nodes else None
            prior_entities = [node for node in prior_nodes if node.node_type == 'entity']
            prior_events = [node for node in prior_nodes if node.node_type == 'event']

            for event_node in event_nodes:
                if previous_event is not None and previous_event.id != event_node.id:
                    self._upsert_edge(
                        edge_cache,
                        branch_id,
                        previous_event,
                        event_node,
                        'follows',
                        chapter_index,
                        metadata_json={'provenance': 'chapter-order'},
                    )
                for entity_node in entity_nodes:
                    self._upsert_edge(
                        edge_cache,
                        branch_id,
                        entity_node,
                        event_node,
                        'participates_in',
                        chapter_index,
                        metadata_json={'provenance': 'same-chapter'},
                    )
                prior_entity_matches = self._matching_nodes(
                    prior_entities,
                    event_node.label,
                    allowed_types={'entity'},
                )
                for prior_entity in prior_entity_matches:
                    self._upsert_edge(
                        edge_cache,
                        branch_id,
                        prior_entity,
                        event_node,
                        'persists_into',
                        chapter_index,
                        metadata_json={'provenance': 'cross-chapter-label-match'},
                    )
                prior_event_matches = self._matching_nodes(
                    prior_events[-8:],
                    event_node.label,
                    allowed_types={'event'},
                )
                for prior_event in prior_event_matches:
                    if prior_event.id == event_node.id:
                        continue
                    self._upsert_edge(
                        edge_cache,
                        branch_id,
                        prior_event,
                        event_node,
                        'advances_to',
                        chapter_index,
                        metadata_json={'provenance': 'cross-chapter-label-match'},
                    )

            self._apply_secondary_node_links(
                branch_id,
                chapter_index,
                edge_cache,
                current_nodes,
                prior_nodes,
                relation_nodes,
                {'entity'},
                'relates_to',
            )
            self._apply_secondary_node_links(
                branch_id,
                chapter_index,
                edge_cache,
                current_nodes,
                prior_nodes,
                relation_nodes,
                {'event'},
                'contextualizes',
            )
            self._apply_secondary_node_links(
                branch_id,
                chapter_index,
                edge_cache,
                current_nodes,
                prior_nodes,
                conflict_nodes,
                {'entity'},
                'conflict_involves',
                reverse_edge_type='pressured_by',
            )
            self._apply_secondary_node_links(
                branch_id,
                chapter_index,
                edge_cache,
                current_nodes,
                prior_nodes,
                conflict_nodes,
                {'event'},
                'conflict_centers_on',
            )
            self._apply_secondary_node_links(
                branch_id,
                chapter_index,
                edge_cache,
                current_nodes,
                prior_nodes,
                foreshadow_nodes,
                {'entity', 'event', 'conflict', 'world_rule'},
                'hints_at',
            )
            self._apply_secondary_node_links(
                branch_id,
                chapter_index,
                edge_cache,
                current_nodes,
                prior_nodes,
                world_rule_nodes,
                {'entity', 'event', 'conflict'},
                'constrains',
            )
            self._apply_secondary_node_links(
                branch_id,
                chapter_index,
                edge_cache,
                current_nodes,
                prior_nodes,
                continuity_nodes,
                {'entity', 'event', 'relation', 'conflict', 'foreshadow', 'world_rule'},
                'carries_forward',
            )

            for conflict_node in conflict_nodes:
                prior_conflict_matches = self._matching_nodes(
                    prior_conflict_nodes[-8:],
                    conflict_node.label,
                    allowed_types={'conflict'},
                )
                for prior_conflict in prior_conflict_matches:
                    if prior_conflict.id == conflict_node.id:
                        continue
                    self._upsert_edge(
                        edge_cache,
                        branch_id,
                        prior_conflict,
                        conflict_node,
                        'escalates_to',
                        chapter_index,
                        metadata_json={'provenance': 'cross-chapter-label-match'},
                    )

            for relation_node in relation_nodes:
                prior_relation_matches = self._matching_nodes(
                    prior_relation_nodes[-8:],
                    relation_node.label,
                    allowed_types={'relation'},
                )
                for prior_relation in prior_relation_matches:
                    if prior_relation.id == relation_node.id:
                        continue
                    self._upsert_edge(
                        edge_cache,
                        branch_id,
                        prior_relation,
                        relation_node,
                        'evolves_to',
                        chapter_index,
                        metadata_json={'provenance': 'cross-chapter-label-match'},
                    )

            payoff_targets = event_nodes + conflict_nodes + relation_nodes + world_rule_nodes
            for payoff_target in payoff_targets:
                for foreshadow_node in self._matching_nodes(
                    prior_foreshadow_nodes,
                    payoff_target.label,
                    allowed_types={'foreshadow'},
                ):
                    self._upsert_edge(
                        edge_cache,
                        branch_id,
                        foreshadow_node,
                        payoff_target,
                        'pays_off_as',
                        chapter_index,
                        metadata_json={'provenance': 'cross-chapter-label-match'},
                    )

            prior_event_nodes.extend(event_nodes)
            prior_conflict_nodes.extend(conflict_nodes)
            prior_relation_nodes.extend(relation_nodes)
            prior_foreshadow_nodes.extend(foreshadow_nodes)
            prior_nodes.extend(current_nodes)

        self.session.commit()
        return list(node_cache.values()), list(edge_cache.values())

    def materialize_for_artifact(self, artifact_id: str) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Rebuild the branch reasoning graph when one artifact changes."""

        artifact = self.session.scalar(
            select(ChapterArtifact).where(ChapterArtifact.id == artifact_id)
        )
        if artifact is None:
            raise ValueError(f"Unknown artifact_id: {artifact_id}")
        return self._rebuild_branch_graph(artifact.branch_id)

    def reasoning_snapshot(
        self,
        branch_id: str,
        *,
        upto_chapter: int | None = None,
        node_limit: int = 20,
        edge_limit: int = 30,
    ) -> dict[str, object]:
        """Return a reasoning-oriented graph snapshot for prompts, QA, and exports."""

        node_stmt = select(GraphNode).where(GraphNode.branch_id == branch_id)
        edge_stmt = select(GraphEdge).where(GraphEdge.branch_id == branch_id)
        if upto_chapter is not None:
            node_stmt = node_stmt.where(GraphNode.chapter_first_seen <= upto_chapter)
            edge_stmt = edge_stmt.where(GraphEdge.chapter_first_seen <= upto_chapter)
        nodes = self.session.scalars(
            node_stmt.order_by(
                GraphNode.chapter_first_seen,
                GraphNode.node_type,
                GraphNode.label,
            )
        ).all()
        edges = self.session.scalars(
            edge_stmt.order_by(
                GraphEdge.chapter_first_seen,
                GraphEdge.edge_type,
            )
        ).all()
        node_by_id = {node.id: node for node in nodes}

        node_type_counts = Counter(node.node_type for node in nodes)
        edge_type_counts = Counter(edge.edge_type for edge in edges)
        degree_counter: Counter[str] = Counter()
        for edge in edges:
            degree_counter[edge.source_node_id] += 1
            degree_counter[edge.target_node_id] += 1

        central_nodes = []
        for node_id, degree in degree_counter.most_common(node_limit):
            node = node_by_id.get(node_id)
            if node is None:
                continue
            central_nodes.append(
                {
                    'label': node.label,
                    'node_type': node.node_type,
                    'degree': degree,
                    'chapter_first_seen': node.chapter_first_seen,
                    'chapter_last_seen': node.chapter_last_seen,
                }
            )

        timeline_edges = []
        reasoning_paths: list[str] = []
        open_foreshadowing: list[str] = []
        active_conflicts: list[str] = []
        world_rules = [node.label for node in nodes if node.node_type == 'world_rule'][:10]
        foreshadow_statuses: list[dict[str, object]] = []
        conflict_statuses: list[dict[str, object]] = []
        relation_statuses: list[dict[str, object]] = []
        payoff_sources = {
            edge.source_node_id
            for edge in edges
            if edge.edge_type == 'pays_off_as'
        }
        escalated_conflicts = {
            edge.source_node_id
            for edge in edges
            if edge.edge_type == 'escalates_to'
        }
        evolved_relations = {
            edge.source_node_id
            for edge in edges
            if edge.edge_type == 'evolves_to'
        }
        constrained_rules = {
            edge.source_node_id
            for edge in edges
            if edge.edge_type == 'constrains'
        }

        for edge in edges:
            source = node_by_id.get(edge.source_node_id)
            target = node_by_id.get(edge.target_node_id)
            if source is None or target is None:
                continue
            if edge.edge_type in {
                'follows',
                'advances_to',
                'escalates_to',
                'evolves_to',
                'pays_off_as',
            }:
                path = f"{source.label} -[{edge.edge_type}]-> {target.label}"
                reasoning_paths.append(path)
                if edge.edge_type in {'follows', 'advances_to'}:
                    timeline_edges.append(path)

        for node in nodes:
            if node.node_type == 'foreshadow' and node.id not in payoff_sources:
                open_foreshadowing.append(node.label)
            if node.node_type == 'conflict':
                active_conflicts.append(node.label)
            if node.node_type == 'foreshadow':
                foreshadow_statuses.append(
                    {
                        'label': node.label,
                        'status': 'paid_off' if node.id in payoff_sources else 'open',
                        'chapter_first_seen': node.chapter_first_seen,
                        'chapter_last_seen': node.chapter_last_seen,
                    }
                )
            if node.node_type == 'conflict':
                if node.id in escalated_conflicts:
                    status = 'escalated'
                elif node.chapter_last_seen == upto_chapter or upto_chapter is None:
                    status = 'active'
                else:
                    status = 'latent'
                conflict_statuses.append(
                    {
                        'label': node.label,
                        'status': status,
                        'chapter_first_seen': node.chapter_first_seen,
                        'chapter_last_seen': node.chapter_last_seen,
                    }
                )
            if node.node_type == 'relation':
                relation_statuses.append(
                    {
                        'label': node.label,
                        'status': 'evolved' if node.id in evolved_relations else 'stable',
                        'chapter_first_seen': node.chapter_first_seen,
                        'chapter_last_seen': node.chapter_last_seen,
                    }
                )

        visible_nodes = sorted(
            nodes,
            key=lambda item: (-degree_counter[item.id], -item.occurrence_count, item.label),
        )[:node_limit]
        visible_node_ids = {node.id for node in visible_nodes}
        visible_edges = [
            edge for edge in edges
            if edge.source_node_id in visible_node_ids or edge.target_node_id in visible_node_ids
        ][:edge_limit]

        return {
            'branch_id': branch_id,
            'upto_chapter': upto_chapter,
            'overview': {
                'node_count': len(nodes),
                'edge_count': len(edges),
                'node_type_counts': dict(node_type_counts),
                'edge_type_counts': dict(edge_type_counts),
            },
            'central_nodes': central_nodes,
            'recent_timeline': timeline_edges[-12:],
            'reasoning_paths': reasoning_paths[:20],
            'active_conflicts': active_conflicts[:12],
            'open_foreshadowing': open_foreshadowing[:12],
            'world_rules': world_rules,
            'state_machine': {
                'foreshadow': foreshadow_statuses[:12],
                'conflict': conflict_statuses[:12],
                'relation': relation_statuses[:12],
                'world_rule': [
                    {
                        'label': node.label,
                        'status': 'constraining' if node.id in constrained_rules else 'observed',
                        'chapter_first_seen': node.chapter_first_seen,
                        'chapter_last_seen': node.chapter_last_seen,
                    }
                    for node in nodes
                    if node.node_type == 'world_rule'
                ][:12],
            },
            'nodes': [
                {
                    'node_type': node.node_type,
                    'label': node.label,
                    'chapter_first_seen': node.chapter_first_seen,
                    'chapter_last_seen': node.chapter_last_seen,
                    'occurrence_count': node.occurrence_count,
                    'metadata': node.metadata_json,
                }
                for node in visible_nodes
            ],
            'edges': [
                {
                    'edge_type': edge.edge_type,
                    'source': (
                        node_by_id[edge.source_node_id].label
                        if edge.source_node_id in node_by_id
                        else edge.source_node_id
                    ),
                    'target': (
                        node_by_id[edge.target_node_id].label
                        if edge.target_node_id in node_by_id
                        else edge.target_node_id
                    ),
                    'weight': edge.weight,
                    'chapter_first_seen': edge.chapter_first_seen,
                    'chapter_last_seen': edge.chapter_last_seen,
                    'metadata': edge.metadata_json,
                }
                for edge in visible_edges
            ],
        }

    def summarize_branch(self, branch_id: str) -> GraphSummary:
        """Return a compact reasoning summary that is easier to inspect than raw rows."""

        snapshot = self.reasoning_snapshot(branch_id)
        overview = cast(dict[str, object], snapshot['overview'])
        nodes = self.session.scalars(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .order_by(GraphNode.node_type, GraphNode.label)
        ).all()
        top_entities = sorted(
            [(node.label, node.occurrence_count) for node in nodes if node.node_type == 'entity'],
            key=lambda item: (-item[1], item[0]),
        )[:10]
        top_events = sorted(
            [(node.label, node.occurrence_count) for node in nodes if node.node_type == 'event'],
            key=lambda item: (-item[1], item[0]),
        )[:10]
        top_conflicts = sorted(
            [(node.label, node.occurrence_count) for node in nodes if node.node_type == 'conflict'],
            key=lambda item: (-item[1], item[0]),
        )[:10]
        return GraphSummary(
            branch_id=branch_id,
            node_count=cast(int, overview['node_count']),
            edge_count=cast(int, overview['edge_count']),
            node_type_counts=cast(dict[str, int], overview['node_type_counts']),
            edge_type_counts=cast(dict[str, int], overview['edge_type_counts']),
            top_entities=top_entities,
            top_events=top_events,
            top_conflicts=top_conflicts,
            progression_edges=cast(list[str], snapshot['recent_timeline']),
            reasoning_paths=cast(list[str], snapshot['reasoning_paths']),
            open_foreshadowing=cast(list[str], snapshot['open_foreshadowing']),
            active_conflicts=cast(list[str], snapshot['active_conflicts']),
            world_rules=cast(list[str], snapshot['world_rules']),
        )
