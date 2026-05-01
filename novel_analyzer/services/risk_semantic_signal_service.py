"""Structured semantic signal builders for risk-audit checkers.

This module keeps semantic-signal extraction separate from checker verdict logic so
future embedding / reranker / canonicalization enhancements can land here without
turning each checker into a black-box model caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import cast

import numpy as np

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import FactRecord
from novel_analyzer.embedding.service import get_embedding_provider


@dataclass(frozen=True, slots=True)
class CommonRiskSignals:
    unsupported: list[str]
    ambiguous: list[str]
    transition_notes: list[str]
    resolutions: list[str]
    unresolved_threads: list[str]
    key_entities: list[str]


@dataclass(frozen=True, slots=True)
class RelationshipSignals:
    stable_relations: list[str]
    evolved_relations: list[str]
    relation_facts: list[str]
    merged_relations: list[str]


@dataclass(frozen=True, slots=True)
class CharacterSignals:
    fact_character_signals: list[str]


@dataclass(frozen=True, slots=True)
class ForeshadowSignals:
    new_foreshadowing: list[str]
    paid_off_foreshadowing: list[str]
    foreshadow_facts: list[str]
    merged_foreshadow: list[str]


@dataclass(frozen=True, slots=True)
class SettingScopeSignals:
    observed_world_rules: list[str]
    constraining_world_rules: list[str]
    rule_facts: list[str]
    merged_scope: list[str]


@dataclass(frozen=True, slots=True)
class RuleSignals:
    rule_signals: list[str]
    artifact_rule_signals: list[str]
    merged_rule_signals: list[str]


@dataclass(frozen=True, slots=True)
class ThreadClosureSignals:
    new_conflicts: list[str]
    escalated_conflicts: list[str]
    conflict_facts: list[str]
    merged_conflicts: list[str]


@dataclass(frozen=True, slots=True)
class PlotSignals:
    structured_signals: dict[str, list[str]]
    structured_signal_bits: list[str]


@dataclass(frozen=True, slots=True)
class TimelineSignals:
    timeline_signals: list[str]
    structured_signals: dict[str, list[str]]
    structured_signal_bits: list[str]


@dataclass(frozen=True, slots=True)
class PowerSignals:
    power_signals: list[str]
    structured_signals: dict[str, list[str]]
    structured_signal_bits: list[str]


class RiskSemanticSignalService:
    """Extract reusable structured signals from artifact/state/fact layers."""

    @staticmethod
    def _dedupe_texts(items: list[str]) -> list[str]:
        return list(dict.fromkeys(item for item in items if item.strip()))

    @staticmethod
    def _text_list(payload: dict[str, object], key: str) -> list[str]:
        return [
            str(x).strip()
            for x in cast(list[object], payload.get(key, []))
            if str(x).strip()
        ]

    @staticmethod
    def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
        return any(token in text for token in tokens)

    @staticmethod
    @lru_cache(maxsize=1)
    def _provider() -> object:
        return get_embedding_provider(get_settings())

    @classmethod
    def _semantic_canonicalize(
        cls,
        texts: list[str],
        *,
        threshold: float = 0.92,
        max_items: int = 24,
    ) -> list[str]:
        deduped = cls._dedupe_texts(texts)
        if len(deduped) <= 1:
            return deduped
        capped = deduped[:max_items]
        try:
            provider = cls._provider()
            vectors = provider.embed_texts(capped)
            if len(vectors) != len(capped):
                return deduped
            matrix = np.asarray(vectors, dtype=np.float32)
            if matrix.ndim != 2:
                return deduped
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms = np.clip(norms, 1e-12, None)
            normalized = matrix / norms
            keep_indices: list[int] = []
            for index, vector in enumerate(normalized):
                duplicate = False
                for kept_index in keep_indices:
                    score = float(np.dot(vector, normalized[kept_index]))
                    if score >= threshold:
                        duplicate = True
                        break
                if not duplicate:
                    keep_indices.append(index)
            canonicalized = [capped[index] for index in keep_indices]
            if len(deduped) > max_items:
                canonicalized.extend(deduped[max_items:])
            return canonicalized
        except Exception:
            return deduped

    @classmethod
    def common_signals(cls, artifact_payload: dict[str, object]) -> CommonRiskSignals:
        return CommonRiskSignals(
            unsupported=cls._text_list(artifact_payload, "unsupported_inferences"),
            ambiguous=cls._text_list(artifact_payload, "ambiguous_points"),
            transition_notes=cls._text_list(artifact_payload, "state_transition_notes"),
            resolutions=cls._text_list(artifact_payload, "evidence_backed_resolutions"),
            unresolved_threads=cls._text_list(artifact_payload, "unresolved_threads"),
            key_entities=cls._text_list(artifact_payload, "key_entities"),
        )

    @classmethod
    def character_signals(
        cls,
        facts: list[FactRecord],
    ) -> CharacterSignals:
        fact_character_signals = [
            fact.label.strip()
            for fact in facts
            if fact.fact_type in {"character_motivation", "character_relation", "character_belief"}
            and fact.label.strip()
        ]
        return CharacterSignals(fact_character_signals=fact_character_signals)

    @classmethod
    def relationship_signals(
        cls,
        artifact_payload: dict[str, object],
        facts: list[FactRecord],
    ) -> RelationshipSignals:
        state_summary = cast(dict[str, object], artifact_payload.get("state_summary", {}))
        stable_relations = cls._text_list(state_summary, "stable_relations")
        evolved_relations = cls._text_list(state_summary, "evolved_relations")
        relation_facts = [
            fact.label.strip()
            for fact in facts
            if fact.fact_type in {"character_relation", "relation"} and fact.label.strip()
        ]
        merged_relations = cls._semantic_canonicalize(stable_relations + evolved_relations + relation_facts)
        return RelationshipSignals(stable_relations, evolved_relations, relation_facts, merged_relations)

    @classmethod
    def foreshadow_signals(
        cls,
        artifact_payload: dict[str, object],
        facts: list[FactRecord],
    ) -> ForeshadowSignals:
        state_summary = cast(dict[str, object], artifact_payload.get("state_summary", {}))
        new_foreshadowing = cls._text_list(state_summary, "new_foreshadowing")
        paid_off_foreshadowing = cls._text_list(state_summary, "paid_off_foreshadowing")
        foreshadow_facts = [
            fact.label.strip()
            for fact in facts
            if fact.fact_type in {"foreshadowing", "foreshadow"} and fact.label.strip()
        ]
        merged_foreshadow = cls._semantic_canonicalize(new_foreshadowing + paid_off_foreshadowing + foreshadow_facts)
        return ForeshadowSignals(new_foreshadowing, paid_off_foreshadowing, foreshadow_facts, merged_foreshadow)

    @classmethod
    def setting_scope_signals(
        cls,
        artifact_payload: dict[str, object],
        facts: list[FactRecord],
    ) -> SettingScopeSignals:
        state_summary = cast(dict[str, object], artifact_payload.get("state_summary", {}))
        observed_world_rules = cls._text_list(state_summary, "observed_world_rules")
        constraining_world_rules = cls._text_list(state_summary, "constraining_world_rules")
        rule_facts = [
            fact.label.strip()
            for fact in facts
            if fact.fact_type in {"world_rule", "setting_scope"} and fact.label.strip()
        ]
        merged_scope = cls._semantic_canonicalize(observed_world_rules + constraining_world_rules + rule_facts)
        return SettingScopeSignals(observed_world_rules, constraining_world_rules, rule_facts, merged_scope)

    @classmethod
    def rule_signals(
        cls,
        artifact_payload: dict[str, object],
        facts: list[FactRecord],
    ) -> RuleSignals:
        rule_signals = [
            fact.label.strip()
            for fact in facts
            if fact.fact_type == "world_rule" and fact.label.strip()
        ]
        artifact_rule_signals = cls._text_list(artifact_payload, "world_rule_signals")
        merged_rule_signals = cls._semantic_canonicalize(rule_signals + artifact_rule_signals)
        return RuleSignals(rule_signals, artifact_rule_signals, merged_rule_signals)

    @classmethod
    def thread_closure_signals(
        cls,
        artifact_payload: dict[str, object],
        facts: list[FactRecord],
    ) -> ThreadClosureSignals:
        state_summary = cast(dict[str, object], artifact_payload.get("state_summary", {}))
        new_conflicts = cls._text_list(state_summary, "new_conflicts")
        escalated_conflicts = cls._text_list(state_summary, "escalated_conflicts")
        conflict_facts = [
            fact.label.strip()
            for fact in facts
            if fact.fact_type in {"conflict", "thread_closure"} and fact.label.strip()
        ]
        merged_conflicts = cls._semantic_canonicalize(new_conflicts + escalated_conflicts + conflict_facts)
        return ThreadClosureSignals(new_conflicts, escalated_conflicts, conflict_facts, merged_conflicts)

    @classmethod
    def plot_signals(
        cls,
        artifact_payload: dict[str, object],
    ) -> PlotSignals:
        common = cls.common_signals(artifact_payload)
        grouped: dict[str, list[str]] = {
            "motivation_like": [],
            "action_like": [],
            "resolved_like": [],
            "unresolved_like": [],
        }
        motivation_tokens = ("动机", "决定", "选择", "态度", "立场")
        action_tokens = ("行动", "出手", "执行", "推进", "结果")
        for text in common.unsupported:
            if cls._contains_any(text, motivation_tokens):
                grouped["motivation_like"].append(text)
            if cls._contains_any(text, action_tokens):
                grouped["action_like"].append(text)
        for text in common.transition_notes:
            if cls._contains_any(text, action_tokens):
                grouped["action_like"].append(text)
        for text in common.resolutions:
            grouped["resolved_like"].append(text)
        for text in common.unresolved_threads:
            grouped["unresolved_like"].append(text)
        summary_bits = [key for key, values in grouped.items() if values]
        return PlotSignals(grouped, summary_bits)

    @classmethod
    def timeline_signals(
        cls,
        artifact_payload: dict[str, object],
    ) -> TimelineSignals:
        common = cls.common_signals(artifact_payload)
        timeline_signals = cls._text_list(artifact_payload, "timeline_signals")
        grouped: dict[str, list[str]] = {
            "same_day": [],
            "next_day": [],
            "multi_day": [],
            "recovery_related": [],
        }
        same_day_tokens = ("当夜", "同夜", "当日", "同日", "当天", "当晚")
        next_day_tokens = ("次日", "翌日", "第二天")
        multi_day_tokens = ("三日后", "数日后", "几日后", "半月后", "一月后", "数月后", "半年后", "一周后")
        recovery_tokens = ("恢复", "痊愈", "闭关", "赶路", "回城", "再出现", "伤势", "时长", "调息")
        for text in timeline_signals:
            if cls._contains_any(text, same_day_tokens):
                grouped["same_day"].append(text)
            if cls._contains_any(text, next_day_tokens):
                grouped["next_day"].append(text)
            if cls._contains_any(text, multi_day_tokens):
                grouped["multi_day"].append(text)
            if cls._contains_any(text, recovery_tokens):
                grouped["recovery_related"].append(text)
        for text in common.unsupported:
            if cls._contains_any(text, recovery_tokens):
                grouped["recovery_related"].append(text)
        summary_bits = [key for key, values in grouped.items() if values]
        return TimelineSignals(timeline_signals, grouped, summary_bits)

    @classmethod
    def power_signals(
        cls,
        artifact_payload: dict[str, object],
    ) -> PowerSignals:
        common = cls.common_signals(artifact_payload)
        power_signals = cls._text_list(artifact_payload, "power_signals")
        grouped: dict[str, list[str]] = {
            "upset_like": [],
            "new_capability": [],
            "cost_constraint": [],
        }
        upset_tokens = ("越阶", "跨级", "压制", "反杀", "碾压")
        new_capability_tokens = ("新招式", "新能力", "突破", "掌握", "跃迁")
        cost_tokens = ("代价", "限制", "消耗", "冷却", "负担", "后遗症")
        for text in power_signals:
            if cls._contains_any(text, upset_tokens):
                grouped["upset_like"].append(text)
            if cls._contains_any(text, new_capability_tokens):
                grouped["new_capability"].append(text)
            if cls._contains_any(text, cost_tokens):
                grouped["cost_constraint"].append(text)
        for text in common.unsupported:
            if cls._contains_any(text, cost_tokens):
                grouped["cost_constraint"].append(text)
        summary_bits = [key for key, values in grouped.items() if values]
        return PowerSignals(power_signals, grouped, summary_bits)
