"""Downstream modular risk-audit framework and chapter risk card aggregation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Protocol, cast

from sqlalchemy import select, update
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from novel_analyzer.database.models import (
    ChapterArtifact,
    ChapterRiskCardRecord,
    FactRecord,
    GateCheckerResultRecord,
)
from novel_analyzer.domain.schemas import ChapterRiskCard, CheckerResult, GateRiskItem
from novel_analyzer.services.risk_signal_cluster_service import RiskSignalClusterService
from novel_analyzer.services.risk_evidence_pack_service import RiskEvidencePackService
from novel_analyzer.services.export_service import ExportService
from novel_analyzer.services.risk_signal_link_service import RiskSignalLinkService
from novel_analyzer.services.risk_semantic_signal_service import RiskSemanticSignalService
from novel_analyzer.services.risk_signal_store_service import RiskSignalStoreService


class GateChecker(Protocol):
    """Contract for one downstream risk checker."""

    name: str
    domain: str

    def evaluate(
        self,
        *,
        branch_id: str,
        chapter_index: int,
        artifact_payload: dict[str, object],
        facts: list[FactRecord],
    ) -> CheckerResult: ...


def _risk_key(*parts: object) -> str:
    return "|".join(str(part).strip() for part in parts if str(part).strip())


def _dedupe_texts(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item.strip()))


@dataclass(slots=True)
class CharacterOOCChecker:
    """Minimal v1 character-OOC checker fed by artifact payload hints."""

    name: str = "character_ooc"
    domain: str = "character"

    @staticmethod
    def _rank_supporting_evidence(items: list[str], *, subtype: str) -> list[str]:
        def score(text: str) -> tuple[int, int]:
            keywords = {
                "relationship_shift_candidate": ["关系", "兄弟", "道侣", "师徒", "亲近", "疏远"],
                "belief_shift_candidate": ["信念", "原则", "底线", "价值", "誓言"],
                "motivation_shift_candidate": ["动机", "态度", "决定", "选择", "立场"],
                "capability_shift_candidate": ["实力", "能力", "招式", "越阶", "压制"],
                "title_only_inference_candidate": ["标题", "无正文", "摘要", "推断"],
                "character_resolution_support_gap": ["解决", "恢复", "兑现"],
                "character_transition_support_gap": ["推进", "转向", "变化"],
                "character_open_thread_candidate": ["未解释", "未解", "线程"],
            }.get(subtype, [])
            hit_count = sum(1 for keyword in keywords if keyword in text)
            return (hit_count, len(text))

        deduped = _dedupe_texts(items)
        return sorted(deduped, key=lambda text: score(text), reverse=True)

    def evaluate(
        self,
        *,
        branch_id: str,
        chapter_index: int,
        artifact_payload: dict[str, object],
        facts: list[FactRecord],
    ) -> CheckerResult:
        start = perf_counter()
        risk_items: list[GateRiskItem] = []
        notes: list[str] = []
        status = "ready"
        common = RiskSemanticSignalService.common_signals(artifact_payload)
        character = RiskSemanticSignalService.character_signals(facts)
        fact_character_signals = character.fact_character_signals
        unsupported = common.unsupported
        ambiguous = common.ambiguous
        transition_notes = common.transition_notes
        resolutions = common.resolutions
        unresolved_threads = common.unresolved_threads
        chapter_summary = str(artifact_payload.get("chapter_summary") or "").strip()
        title_only_hint = any(
            token in text
            for text in [chapter_summary] + unsupported + ambiguous
            for token in ["无正文", "仅提供章节标题", "仅有标题", "基于标题", "无法提供有效总结"]
        )
        custom_candidates = cast(list[object], artifact_payload.get("ooc_candidates", []))
        for item in custom_candidates:
            if not isinstance(item, dict):
                continue
            character_name = str(item.get("character_name") or item.get("character") or "").strip()
            risk_type = str(item.get("risk_type") or "").strip()
            summary = str(item.get("summary") or "").strip()
            if not (character_name and risk_type and summary):
                continue
            supporting = [str(x).strip() for x in cast(list[object], item.get("supporting_evidence", [])) if str(x).strip()]
            counter = [str(x).strip() for x in cast(list[object], item.get("counter_evidence", [])) if str(x).strip()]
            risk_items.append(
                GateRiskItem(
                    checker_name=self.name,
                    risk_domain=self.domain,
                    risk_type=risk_type,
                    severity=str(item.get("severity") or "medium"),
                    confidence=float(item.get("confidence") or 0.6),
                    summary=summary,
                    supporting_evidence=supporting,
                    counter_evidence=counter,
                    related_entities=[character_name],
                    related_chapters=[chapter_index],
                    needs_human_review=bool(item.get("needs_human_review", True)),
                    risk_key=_risk_key(branch_id, chapter_index, self.name, character_name, risk_type, summary[:80]),
                )
            )

        if not risk_items:
            derived_supporting: list[str] = []
            derived_counter: list[str] = []
            derived_type = "human_review_candidate"
            derived_summary = "本章存在人物连续性上的可疑点，需要人工复核。"
            subtype_source = " ".join(
                unsupported
                + ambiguous
                + transition_notes
                + resolutions
                + unresolved_threads
                + fact_character_signals
            )
            if any(token in subtype_source for token in ["关系", "兄弟", "道侣", "师徒", "亲近", "疏远"]):
                derived_type = "relationship_shift_candidate"
                derived_summary = "本章存在人物关系变化上的可疑点，建议人工复核。"
            elif any(token in subtype_source for token in ["信念", "原则", "底线", "价值", "誓言"]):
                derived_type = "belief_shift_candidate"
                derived_summary = "本章存在人物信念/原则变化上的可疑点，建议人工复核。"
            elif any(token in subtype_source for token in ["动机", "态度", "决定", "选择", "立场"]):
                derived_type = "motivation_shift_candidate"
                derived_summary = "本章存在人物动机/态度变化上的可疑点，建议人工复核。"
            elif any(token in subtype_source for token in ["实力", "能力", "招式", "越阶", "压制"]):
                derived_type = "capability_shift_candidate"
                derived_summary = "本章存在人物能力/表现变化上的可疑点，建议人工复核。"
            if unsupported and title_only_hint:
                derived_supporting = unsupported[:2]
                derived_counter = ["当前更像标题/摘要层推断过强，尚不足以自动确认人物 OOC。"]
                derived_type = "title_only_inference_candidate"
                derived_summary = "本章可能主要依赖标题/摘要推断人物变化，建议人工复核。"
            elif unsupported and resolutions:
                derived_supporting = (unsupported[:1] + resolutions[:1])[:2]
                derived_counter = ["当前人物变化与“已解决/已兑现”类表述之间仍可能存在解释空间。"]
                derived_type = "character_resolution_support_gap"
                derived_summary = "本章人物状态变化与解决性表述之间存在支撑缺口，建议人工复核。"
            elif unsupported and transition_notes:
                derived_supporting = (unsupported[:1] + transition_notes[:1])[:2]
                derived_counter = ["当前人物变化可能是推进摘要过强，并不必然构成 OOC。"]
                if derived_type == "relationship_shift_candidate":
                    derived_summary = "本章人物关系变化与推进结论之间存在可疑缺口，建议人工复核。"
                elif derived_type == "belief_shift_candidate":
                    derived_summary = "本章人物信念/原则变化与推进结论之间存在可疑缺口，建议人工复核。"
                elif derived_type == "motivation_shift_candidate":
                    derived_summary = "本章人物动机/态度变化与推进结论之间存在可疑缺口，建议人工复核。"
                elif derived_type == "capability_shift_candidate":
                    derived_summary = "本章人物能力/表现变化与推进结论之间存在可疑缺口，建议人工复核。"
                else:
                    derived_type = "character_transition_support_gap"
                    derived_summary = "本章人物推进结论与证据支撑之间存在可疑缺口，建议人工复核。"
            elif ambiguous and unresolved_threads:
                derived_supporting = (ambiguous[:1] + unresolved_threads[:1])[:2]
                derived_counter = ["当前更像人物相关未闭合线程，而不是可直接确认的人设崩坏。"]
                if derived_type == "relationship_shift_candidate":
                    derived_summary = "本章人物关系变化存在未闭合线程，建议人工复核。"
                elif derived_type == "belief_shift_candidate":
                    derived_summary = "本章人物信念/原则变化存在未闭合线程，建议人工复核。"
                elif derived_type == "motivation_shift_candidate":
                    derived_summary = "本章人物动机/态度变化存在未闭合线程，建议人工复核。"
                elif derived_type == "capability_shift_candidate":
                    derived_summary = "本章人物能力/表现变化存在未闭合线程，建议人工复核。"
                else:
                    derived_type = "character_open_thread_candidate"
                    derived_summary = "本章存在人物连续性未闭合线程，建议人工复核。"
            elif ambiguous or unsupported:
                derived_supporting = ambiguous[:2] or unsupported[:2]
                derived_counter = ["当前仅有摘要级信号，尚不足以自动确认人物 OOC。"]
            elif fact_character_signals:
                derived_supporting = fact_character_signals[:2]
                derived_counter = ["当前只有弱角色信号，先保持提示级别。"]

            if artifact_payload.get("needs_human_review") and (derived_supporting or fact_character_signals):
                supporting = derived_supporting or fact_character_signals[:2]
                supporting = self._rank_supporting_evidence(supporting, subtype=derived_type)[:2]
                risk_items.append(
                    GateRiskItem(
                        checker_name=self.name,
                        risk_domain=self.domain,
                        risk_type=derived_type,
                        severity="low",
                        confidence=0.22 if derived_type == "title_only_inference_candidate" else 0.35,
                        summary=derived_summary,
                        supporting_evidence=supporting,
                        counter_evidence=derived_counter or ["当前仅有摘要级信号，尚不足以自动确认人物 OOC。"],
                        related_entities=fact_character_signals[:2],
                        related_chapters=[chapter_index],
                        needs_human_review=True,
                        risk_key=_risk_key(branch_id, chapter_index, self.name, derived_type),
                    )
                )
                status = "partial"
                notes.append("检测到弱角色信号，已结合 artifact 推进/解决/未解字段降级为人工复核候选。")
            else:
                status = "skipped"
                notes.append("缺少足够的角色连续性信号，当前跳过 OOC 风险生成。")
        elif custom_candidates and not fact_character_signals:
            status = "partial"
            notes.append("当前主要依赖 artifact hint 生成 OOC 风险，尚未建立稳定角色信号真源。")

        return CheckerResult(
            checker_name=self.name,
            chapter_index=chapter_index,
            status=status,
            risks=risk_items,
            notes=notes,
            latency_ms=int((perf_counter() - start) * 1000),
        )


@dataclass(slots=True)
class WorldRuleConsistencyChecker:
    """Minimal v1 rule-consistency checker using artifact hints and facts."""

    name: str = "world_rule_consistency"
    domain: str = "rules"

    @staticmethod
    def _rank_supporting_evidence(items: list[str], *, subtype: str) -> list[str]:
        def score(text: str) -> tuple[int, int]:
            keywords = {
                "rule_exception_candidate": ["例外", "阶段性", "暂时", "特殊条件", "一次性", "条件触发"],
                "rule_support_gap": ["规则", "限制", "门槛", "约束", "证据"],
                "rule_ambiguity_candidate": ["歧义", "含混", "不清", "例外"],
                "rule_resolution_candidate": ["解除", "解决", "不再成立", "失效"],
                "rule_open_thread_candidate": ["未解释", "未解", "线程"],
                "rule_review_candidate": ["规则", "限制", "门槛", "约束"],
                "rule_consistency": ["规则", "限制", "门槛", "约束"],
            }.get(subtype, [])
            hit_count = sum(1 for keyword in keywords if keyword in text)
            return (hit_count, len(text))

        deduped = _dedupe_texts(items)
        return sorted(deduped, key=lambda text: score(text), reverse=True)

    def evaluate(
        self,
        *,
        branch_id: str,
        chapter_index: int,
        artifact_payload: dict[str, object],
        facts: list[FactRecord],
    ) -> CheckerResult:
        start = perf_counter()
        risk_items: list[GateRiskItem] = []
        notes: list[str] = []
        status = "ready"
        common = RiskSemanticSignalService.common_signals(artifact_payload)
        rule = RiskSemanticSignalService.rule_signals(artifact_payload, facts)
        rule_signals = rule.rule_signals
        artifact_rule_signals = rule.artifact_rule_signals
        merged_rule_signals = rule.merged_rule_signals
        unsupported = common.unsupported
        ambiguous = common.ambiguous
        resolutions = common.resolutions
        unresolved_threads = common.unresolved_threads
        custom_issues = cast(list[object], artifact_payload.get("world_rule_issues", []))
        for item in custom_issues:
            if not isinstance(item, dict):
                continue
            rule_key = str(item.get("rule_key") or item.get("rule_name") or "").strip()
            summary = str(item.get("summary") or "").strip()
            if not summary:
                continue
            supporting = [str(x).strip() for x in cast(list[object], item.get("supporting_evidence", [])) if str(x).strip()]
            counter = [str(x).strip() for x in cast(list[object], item.get("counter_evidence", [])) if str(x).strip()]
            related_entities = [str(x).strip() for x in cast(list[object], item.get("related_entities", [])) if str(x).strip()]
            if not supporting and merged_rule_signals:
                supporting = merged_rule_signals[:2]
            if not related_entities and (rule_key or merged_rule_signals):
                related_entities = ([rule_key] if rule_key else []) + merged_rule_signals[:2]
            risk_items.append(
                GateRiskItem(
                    checker_name=self.name,
                    risk_domain=self.domain,
                    risk_type=str(item.get("risk_type") or "rule_consistency"),
                    severity=str(item.get("severity") or "medium"),
                    confidence=float(item.get("confidence") or 0.6),
                    summary=summary,
                    supporting_evidence=self._rank_supporting_evidence(
                        supporting,
                        subtype=str(item.get("risk_type") or "rule_consistency"),
                    ),
                    counter_evidence=_dedupe_texts(counter),
                    related_entities=_dedupe_texts(related_entities),
                    related_chapters=[chapter_index],
                    needs_human_review=bool(item.get("needs_human_review", True)),
                    risk_key=_risk_key(branch_id, chapter_index, self.name, rule_key or "rule", summary[:80]),
                )
            )

        if not risk_items:
            derived_supporting: list[str] = []
            derived_counter: list[str] = []
            derived_type = "rule_review_candidate"
            derived_summary = "本章涉及规则设定信号，建议做一致性人工复核。"
            exception_hint = any(
                token in text
                for text in ambiguous + unsupported + resolutions
                for token in ["例外", "阶段性", "暂时", "特殊条件", "一次性", "条件触发"]
            )
            if merged_rule_signals and unsupported and exception_hint:
                derived_supporting = (merged_rule_signals[:1] + unsupported[:1])[:2]
                derived_counter = ["当前更像规则例外或条件触发，尚不足以直接确认规则冲突。"]
                derived_type = "rule_exception_candidate"
                derived_summary = "本章规则变化更像例外条件或阶段性变化，建议人工复核。"
            elif merged_rule_signals and unsupported:
                derived_supporting = (merged_rule_signals[:1] + unsupported[:1])[:2]
                derived_counter = ["当前规则结论与证据约束之间仍可能存在解释空间。"]
                derived_type = "rule_support_gap"
                derived_summary = "本章规则设定存在支撑缺口，建议人工复核。"
            elif merged_rule_signals and ambiguous:
                derived_supporting = (merged_rule_signals[:1] + ambiguous[:1])[:2]
                derived_counter = ["当前更像规则表述含混，尚不足以直接确认规则冲突。"]
                derived_type = "rule_ambiguity_candidate"
                derived_summary = "本章规则表述存在歧义，建议人工复核。"
            elif merged_rule_signals and resolutions:
                derived_supporting = (merged_rule_signals[:1] + resolutions[:1])[:2]
                derived_counter = ["当前规则限制与“已解决/已解除”类表述之间可能仍有解释空间。"]
                derived_type = "rule_resolution_candidate"
                derived_summary = "本章规则限制与解决性表述之间存在可疑点，建议人工复核。"
            elif merged_rule_signals and unresolved_threads:
                derived_supporting = (merged_rule_signals[:1] + unresolved_threads[:1])[:2]
                derived_counter = ["当前更像规则相关未闭合线程，而不是已确认规则冲突。"]
                derived_type = "rule_open_thread_candidate"
                derived_summary = "本章存在规则相关未闭合线程，建议人工复核。"
            elif merged_rule_signals:
                derived_supporting = merged_rule_signals[:2]
                derived_counter = ["当前缺少明确的规则冲突证据，先保持提示级别。"]

            if artifact_payload.get("needs_human_review") and derived_supporting:
                derived_supporting = self._rank_supporting_evidence(derived_supporting, subtype=derived_type)[:2]
                risk_items.append(
                    GateRiskItem(
                        checker_name=self.name,
                        risk_domain=self.domain,
                        risk_type=derived_type,
                        severity="low",
                        confidence=0.3,
                        summary=derived_summary,
                        supporting_evidence=derived_supporting,
                        counter_evidence=derived_counter,
                        related_entities=merged_rule_signals[:2],
                        related_chapters=[chapter_index],
                        needs_human_review=True,
                        risk_key=_risk_key(branch_id, chapter_index, self.name, derived_type),
                    )
                )
                status = "partial"
                notes.append("检测到弱规则信号，已结合 artifact 规则/解决/未解字段降级为人工复核候选。")
            else:
                status = "skipped"
                notes.append("缺少足够的规则信号，当前跳过规则一致性风险生成。")
        elif custom_issues and not (rule_signals or artifact_rule_signals):
            status = "partial"
            notes.append("当前主要依赖 artifact hint 生成规则风险，尚未建立稳定规则信号真源。")

        return CheckerResult(
            checker_name=self.name,
            chapter_index=chapter_index,
            status=status,
            risks=risk_items,
            notes=notes,
            latency_ms=int((perf_counter() - start) * 1000),
        )


@dataclass(slots=True)
class RelationshipConsistencyChecker:
    """Phase-2 relationship checker focused on bridge/support gaps, not subjective judgement."""

    name: str = "relationship_consistency"
    domain: str = "relationship"
    retrieval_search: object | None = None

    @staticmethod
    def _rank_supporting_evidence(items: list[str], *, subtype: str) -> list[str]:
        def score(text: str) -> tuple[int, int]:
            keywords = {
                "relationship_shift_without_bridge": ["关系", "亲近", "疏远", "师徒", "兄弟", "敌对", "和解", "信任"],
                "trust_state_conflict": ["信任", "怀疑", "敌意", "和解", "已解决", "未解", "关系"],
                "hostility_resolution_too_fast": ["敌对", "仇怨", "和解", "握手言和", "冰释前嫌", "亲近"],
                "relationship_support_gap": ["关系", "变化", "支撑", "桥段", "前置"],
                "relationship_ambiguity_candidate": ["关系", "歧义", "含混", "态度"],
                "relationship_open_thread_candidate": ["关系", "未解", "线程", "后续"],
                "relationship_review_candidate": ["关系", "亲近", "疏远", "信任"],
            }.get(subtype, [])
            hit_count = sum(1 for keyword in keywords if keyword in text)
            return (hit_count, len(text))

        deduped = _dedupe_texts(items)
        return sorted(deduped, key=lambda text: score(text), reverse=True)

    @staticmethod
    def _artifact_relation_signals(artifact_payload: dict[str, object]) -> tuple[list[str], list[str]]:
        state_summary = cast(dict[str, object], artifact_payload.get("state_summary", {}))
        stable_relations = [
            str(x).strip()
            for x in cast(list[object], state_summary.get("stable_relations", []))
            if str(x).strip()
        ]
        evolved_relations = [
            str(x).strip()
            for x in cast(list[object], state_summary.get("evolved_relations", []))
            if str(x).strip()
        ]
        return stable_relations, evolved_relations

    @staticmethod
    def _looks_like_hostility_resolution(text: str) -> bool:
        hostility_tokens = ("敌对", "仇", "死敌", "对立", "互不信任", "反目")
        soften_tokens = ("和解", "亲近", "握手言和", "冰释前嫌", "信任", "结盟", "兄弟", "道侣")
        return any(token in text for token in hostility_tokens) and any(token in text for token in soften_tokens)

    def evaluate(
        self,
        *,
        branch_id: str,
        chapter_index: int,
        artifact_payload: dict[str, object],
        facts: list[FactRecord],
    ) -> CheckerResult:
        start = perf_counter()
        risk_items: list[GateRiskItem] = []
        notes: list[str] = []
        status = "ready"
        common = RiskSemanticSignalService.common_signals(artifact_payload)
        relationship = RiskSemanticSignalService.relationship_signals(artifact_payload, facts)
        stable_relations, evolved_relations = relationship.stable_relations, relationship.evolved_relations
        relation_facts = relationship.relation_facts
        merged_relations = relationship.merged_relations
        unsupported = common.unsupported
        ambiguous = common.ambiguous
        transition_notes = common.transition_notes
        resolutions = common.resolutions
        unresolved_threads = common.unresolved_threads
        key_entities = common.key_entities
        custom_issues = cast(list[object], artifact_payload.get("relationship_issues", []))
        for item in custom_issues:
            if not isinstance(item, dict):
                continue
            summary = str(item.get("summary") or "").strip()
            if not summary:
                continue
            related_entities = [
                str(x).strip() for x in cast(list[object], item.get("related_entities", [])) if str(x).strip()
            ]
            if not related_entities:
                related_entities = key_entities[:2]
            risk_items.append(
                GateRiskItem(
                    checker_name=self.name,
                    risk_domain=self.domain,
                    risk_type=str(item.get("risk_type") or "relationship_review_candidate"),
                    severity=str(item.get("severity") or "medium"),
                    confidence=float(item.get("confidence") or 0.55),
                    summary=summary,
                    supporting_evidence=self._rank_supporting_evidence(
                        [str(x).strip() for x in cast(list[object], item.get("supporting_evidence", [])) if str(x).strip()],
                        subtype=str(item.get("risk_type") or "relationship_review_candidate"),
                    ),
                    counter_evidence=_dedupe_texts(
                        [str(x).strip() for x in cast(list[object], item.get("counter_evidence", [])) if str(x).strip()]
                    ),
                    related_entities=related_entities,
                    related_chapters=[chapter_index],
                    needs_human_review=bool(item.get("needs_human_review", True)),
                    risk_key=_risk_key(branch_id, chapter_index, self.name, summary[:80]),
                )
            )

        if not risk_items:
            relation_change_hint = bool(evolved_relations or relation_facts)
            derived_supporting: list[str] = []
            derived_counter: list[str] = []
            derived_type = "relationship_review_candidate"
            derived_summary = "本章存在人物关系变化信号，建议做一致性人工复核。"

            if relation_change_hint and unsupported and resolutions and unresolved_threads:
                derived_supporting = (evolved_relations[:1] + resolutions[:1] + unresolved_threads[:1] + unsupported[:1])[:4]
                derived_counter = ["当前也可能只是阶段性缓和/破裂，仍需结合前后文确认关系状态是否真的冲突。"]
                derived_type = "trust_state_conflict"
                derived_summary = "本章人物关系同时出现缓和/已解决与未解对立信号，建议人工复核。"
            elif relation_change_hint and any(self._looks_like_hostility_resolution(text) for text in merged_relations) and (
                ambiguous or unsupported or resolutions
            ):
                derived_supporting = (
                    [text for text in merged_relations if self._looks_like_hostility_resolution(text)][:1]
                    + (ambiguous[:1] or unsupported[:1] or resolutions[:1])
                )[:2]
                derived_counter = ["当前也可能省略了中间和解桥段，仍需回看前后章确认关系缓和速度。"]
                derived_type = "hostility_resolution_too_fast"
                derived_summary = "本章敌对关系缓和过快，桥接证据不足，建议人工复核。"
            elif relation_change_hint and unsupported and transition_notes:
                derived_supporting = (evolved_relations[:1] + unsupported[:1] + transition_notes[:1])[:3]
                if self.retrieval_search is not None and evolved_relations:
                    try:
                        pack = self.retrieval_search(
                            branch_id=branch_id,
                            chapter_index=chapter_index,
                            query_text=evolved_relations[0],
                            signal_type='relationship',
                            limit=2,
                        )
                        derived_supporting = (
                            derived_supporting
                            + pack.support_texts
                            + pack.state_summaries
                            + pack.exact_hints
                            + [f"object:{item.object_type}:{item.label}" for item in pack.latest_objects]
                        )[:6]
                    except Exception:
                        pass
                derived_counter = ["当前关系变化也可能由前章信息触发，尚不足以直接确认关系口径跳变。"]
                derived_type = "relationship_shift_without_bridge"
                derived_summary = "本章人物关系发生明显变化，但桥接支撑不足，建议人工复核。"
            elif relation_change_hint and unsupported:
                derived_supporting = (merged_relations[:1] + unsupported[:1])[:2]
                derived_counter = ["当前关系变化结论与正文支撑之间仍可能存在解释空间。"]
                derived_type = "relationship_support_gap"
                derived_summary = "本章人物关系变化存在支撑缺口，建议人工复核。"
            elif relation_change_hint and ambiguous:
                derived_supporting = (merged_relations[:1] + ambiguous[:1])[:2]
                derived_counter = ["当前更像关系表述含混，尚不足以直接确认关系跳变。"]
                derived_type = "relationship_ambiguity_candidate"
                derived_summary = "本章人物关系表述存在歧义，建议人工复核。"
            elif relation_change_hint and unresolved_threads:
                derived_supporting = (merged_relations[:1] + unresolved_threads[:1])[:2]
                derived_counter = ["当前更像关系线未闭合，而不是已确认关系冲突。"]
                derived_type = "relationship_open_thread_candidate"
                derived_summary = "本章存在未闭合的人物关系线程，建议人工复核。"
            elif merged_relations:
                derived_supporting = merged_relations[:2]
                derived_counter = ["当前缺少稳定的跨章节关系冲突证据，先保持提示级别。"]

            if artifact_payload.get("needs_human_review") and derived_supporting:
                risk_items.append(
                    GateRiskItem(
                        checker_name=self.name,
                        risk_domain=self.domain,
                        risk_type=derived_type,
                        severity="low",
                        confidence=0.3,
                        summary=derived_summary,
                        supporting_evidence=self._rank_supporting_evidence(derived_supporting, subtype=derived_type)[:3],
                        counter_evidence=derived_counter,
                        related_entities=key_entities[:2],
                        related_chapters=[chapter_index],
                        needs_human_review=True,
                        risk_key=_risk_key(branch_id, chapter_index, self.name, derived_type),
                    )
                )
                status = "partial"
                notes.append("检测到弱关系变化信号，已结合 state_summary / artifact 证据约束降级为人工复核候选。")
            else:
                status = "skipped"
                notes.append("缺少足够的人物关系信号，当前跳过关系一致性风险生成。")
        elif custom_issues and not merged_relations:
            status = "partial"
            notes.append("当前主要依赖 artifact hint 生成人物关系风险，尚未建立稳定关系信号真源。")

        return CheckerResult(
            checker_name=self.name,
            chapter_index=chapter_index,
            status=status,
            risks=risk_items,
            notes=notes,
            latency_ms=int((perf_counter() - start) * 1000),
        )


@dataclass(slots=True)
class ForeshadowPayoffChecker:
    """Phase-2 foreshadow/payoff checker focused on setup/payoff continuity."""

    name: str = "foreshadow_payoff_consistency"
    domain: str = "foreshadow"
    retrieval_search: object | None = None

    @staticmethod
    def _rank_supporting_evidence(items: list[str], *, subtype: str) -> list[str]:
        def score(text: str) -> tuple[int, int]:
            keywords = {
                "payoff_without_setup": ["伏笔", "铺垫", "兑现", "突然", "回收"],
                "resolved_thread_reopened_without_reason": ["已解决", "重开", "未解", "线程", "伏笔"],
                "important_thread_long_unmentioned": ["长期", "未提", "搁置", "伏笔", "线程"],
                "foreshadow_support_gap": ["伏笔", "铺垫", "支撑", "回收"],
                "foreshadow_ambiguity_candidate": ["伏笔", "歧义", "含混", "暗示"],
                "foreshadow_open_thread_candidate": ["伏笔", "未解", "线程", "后续"],
                "foreshadow_review_candidate": ["伏笔", "铺垫", "兑现", "回收"],
            }.get(subtype, [])
            hit_count = sum(1 for keyword in keywords if keyword in text)
            return (hit_count, len(text))

        deduped = _dedupe_texts(items)
        return sorted(deduped, key=lambda text: score(text), reverse=True)

    @staticmethod
    def _artifact_foreshadow_signals(artifact_payload: dict[str, object]) -> tuple[list[str], list[str]]:
        state_summary = cast(dict[str, object], artifact_payload.get("state_summary", {}))
        new_foreshadowing = [
            str(x).strip()
            for x in cast(list[object], state_summary.get("new_foreshadowing", []))
            if str(x).strip()
        ]
        paid_off_foreshadowing = [
            str(x).strip()
            for x in cast(list[object], state_summary.get("paid_off_foreshadowing", []))
            if str(x).strip()
        ]
        return new_foreshadowing, paid_off_foreshadowing

    def evaluate(
        self,
        *,
        branch_id: str,
        chapter_index: int,
        artifact_payload: dict[str, object],
        facts: list[FactRecord],
    ) -> CheckerResult:
        start = perf_counter()
        risk_items: list[GateRiskItem] = []
        notes: list[str] = []
        status = "ready"
        common = RiskSemanticSignalService.common_signals(artifact_payload)
        foreshadow = RiskSemanticSignalService.foreshadow_signals(artifact_payload, facts)
        new_foreshadowing = foreshadow.new_foreshadowing
        paid_off_foreshadowing = foreshadow.paid_off_foreshadowing
        foreshadow_facts = foreshadow.foreshadow_facts
        merged_foreshadow = foreshadow.merged_foreshadow
        unsupported = common.unsupported
        ambiguous = common.ambiguous
        resolutions = common.resolutions
        unresolved_threads = common.unresolved_threads
        custom_issues = cast(list[object], artifact_payload.get("foreshadow_payoff_issues", []))
        for item in custom_issues:
            if not isinstance(item, dict):
                continue
            summary = str(item.get("summary") or "").strip()
            if not summary:
                continue
            risk_items.append(
                GateRiskItem(
                    checker_name=self.name,
                    risk_domain=self.domain,
                    risk_type=str(item.get("risk_type") or "foreshadow_review_candidate"),
                    severity=str(item.get("severity") or "medium"),
                    confidence=float(item.get("confidence") or 0.55),
                    summary=summary,
                    supporting_evidence=self._rank_supporting_evidence(
                        [str(x).strip() for x in cast(list[object], item.get("supporting_evidence", [])) if str(x).strip()],
                        subtype=str(item.get("risk_type") or "foreshadow_review_candidate"),
                    ),
                    counter_evidence=_dedupe_texts(
                        [str(x).strip() for x in cast(list[object], item.get("counter_evidence", [])) if str(x).strip()]
                    ),
                    related_entities=_dedupe_texts(
                        [str(x).strip() for x in cast(list[object], item.get("related_entities", [])) if str(x).strip()]
                    ),
                    related_chapters=[chapter_index],
                    needs_human_review=bool(item.get("needs_human_review", True)),
                    risk_key=_risk_key(branch_id, chapter_index, self.name, summary[:80]),
                )
            )

        if not risk_items:
            derived_supporting: list[str] = []
            derived_counter: list[str] = []
            derived_type = "foreshadow_review_candidate"
            derived_summary = "本章存在伏笔/兑现信号，建议做一致性人工复核。"

            if paid_off_foreshadowing and unsupported and not new_foreshadowing:
                derived_supporting = (paid_off_foreshadowing[:1] + unsupported[:1])[:2]
                if self.retrieval_search is not None and paid_off_foreshadowing:
                    try:
                        pack = self.retrieval_search(
                            branch_id=branch_id,
                            chapter_index=chapter_index,
                            query_text=paid_off_foreshadowing[0],
                            signal_type='foreshadow',
                            limit=2,
                        )
                        derived_supporting = (
                            derived_supporting
                            + pack.support_texts
                            + pack.state_summaries
                            + pack.exact_hints
                            + [f"object:{item.object_type}:{item.label}" for item in pack.latest_objects]
                        )[:5]
                    except Exception:
                        pass
                derived_counter = ["当前也可能是前文铺垫分散在更早章节，仍需结合跨章节上下文复核。"]
                derived_type = "payoff_without_setup"
                derived_summary = "本章重要结果突然兑现，但前置铺垫不足，建议人工复核。"
            elif paid_off_foreshadowing and unresolved_threads and resolutions:
                derived_supporting = (paid_off_foreshadowing[:1] + resolutions[:1] + unresolved_threads[:1])[:3]
                derived_counter = ["当前也可能只是阶段性兑现后保留更大母题，仍需结合后续章节复核。"]
                derived_type = "resolved_thread_reopened_without_reason"
                derived_summary = "本章已兑现/已解决的线索又以未解线程形式回返，建议人工复核。"
            elif new_foreshadowing and unresolved_threads and ambiguous and not paid_off_foreshadowing:
                derived_supporting = (new_foreshadowing[:1] + unresolved_threads[:1] + ambiguous[:1])[:3]
                derived_counter = ["当前也可能只是作者刻意延后回收，仍需结合更长区间判断。"]
                derived_type = "important_thread_long_unmentioned"
                derived_summary = "本章关键伏笔/线程仍长期悬置且解释不足，建议人工复核。"
            elif merged_foreshadow and unsupported:
                derived_supporting = (merged_foreshadow[:1] + unsupported[:1])[:2]
                derived_counter = ["当前伏笔兑现结论与正文支撑之间仍可能存在解释空间。"]
                derived_type = "foreshadow_support_gap"
                derived_summary = "本章伏笔/兑现链条存在支撑缺口，建议人工复核。"
            elif merged_foreshadow and ambiguous:
                derived_supporting = (merged_foreshadow[:1] + ambiguous[:1])[:2]
                derived_counter = ["当前更像伏笔表述含混，尚不足以直接确认铺垫/回收异常。"]
                derived_type = "foreshadow_ambiguity_candidate"
                derived_summary = "本章伏笔/兑现表述存在歧义，建议人工复核。"
            elif merged_foreshadow and unresolved_threads:
                derived_supporting = (merged_foreshadow[:1] + unresolved_threads[:1])[:2]
                derived_counter = ["当前更像未闭合的伏笔线程，而不是已确认问题。"]
                derived_type = "foreshadow_open_thread_candidate"
                derived_summary = "本章存在未闭合的伏笔/兑现线程，建议人工复核。"
            elif merged_foreshadow:
                derived_supporting = merged_foreshadow[:2]
                derived_counter = ["当前缺少稳定的跨章节伏笔生命周期证据，先保持提示级别。"]

            if artifact_payload.get("needs_human_review") and derived_supporting:
                risk_items.append(
                    GateRiskItem(
                        checker_name=self.name,
                        risk_domain=self.domain,
                        risk_type=derived_type,
                        severity="low",
                        confidence=0.3,
                        summary=derived_summary,
                        supporting_evidence=self._rank_supporting_evidence(derived_supporting, subtype=derived_type)[:3],
                        counter_evidence=derived_counter,
                        related_entities=[],
                        related_chapters=[chapter_index],
                        needs_human_review=True,
                        risk_key=_risk_key(branch_id, chapter_index, self.name, derived_type),
                    )
                )
                status = "partial"
                notes.append("检测到弱伏笔/兑现信号，已结合 state_summary / artifact 证据约束降级为人工复核候选。")
            else:
                status = "skipped"
                notes.append("缺少足够的伏笔/兑现信号，当前跳过伏笔一致性风险生成。")
        elif custom_issues and not merged_foreshadow:
            status = "partial"
            notes.append("当前主要依赖 artifact hint 生成伏笔/兑现风险，尚未建立稳定伏笔生命周期真源。")

        return CheckerResult(
            checker_name=self.name,
            chapter_index=chapter_index,
            status=status,
            risks=risk_items,
            notes=notes,
            latency_ms=int((perf_counter() - start) * 1000),
        )


@dataclass(slots=True)
class SettingScopeConsistencyChecker:
    """Phase-2 setting-scope checker for scope expansion / limit drift / boundary conflict."""

    name: str = "setting_scope_consistency"
    domain: str = "setting_scope"
    retrieval_search: object | None = None

    @staticmethod
    def _rank_supporting_evidence(items: list[str], *, subtype: str) -> list[str]:
        def score(text: str) -> tuple[int, int]:
            keywords = {
                "constraint_scope_expansion": ["范围", "全城", "全域", "所有", "任意", "无限", "权限"],
                "resource_limit_missing": ["资源", "次数", "消耗", "限制", "额度", "代价", "冷却"],
                "authority_boundary_conflict": ["权限", "边界", "禁地", "组织", "阵营", "资格", "许可"],
                "setting_scope_support_gap": ["范围", "限制", "边界", "支撑"],
                "setting_scope_ambiguity_candidate": ["范围", "歧义", "含混", "边界"],
                "setting_scope_open_thread_candidate": ["范围", "未解", "线程", "后续"],
                "setting_scope_review_candidate": ["范围", "限制", "权限", "边界"],
            }.get(subtype, [])
            hit_count = sum(1 for keyword in keywords if keyword in text)
            return (hit_count, len(text))

        deduped = _dedupe_texts(items)
        return sorted(deduped, key=lambda text: score(text), reverse=True)

    @staticmethod
    def _artifact_scope_signals(artifact_payload: dict[str, object]) -> tuple[list[str], list[str]]:
        state_summary = cast(dict[str, object], artifact_payload.get("state_summary", {}))
        observed = [
            str(x).strip()
            for x in cast(list[object], state_summary.get("observed_world_rules", []))
            if str(x).strip()
        ]
        constraining = [
            str(x).strip()
            for x in cast(list[object], state_summary.get("constraining_world_rules", []))
            if str(x).strip()
        ]
        return observed, constraining

    @staticmethod
    def _looks_like_scope_expansion(text: str) -> bool:
        return any(token in text for token in ("全城", "全域", "所有", "任意", "无限", "全面开放", "无条件"))

    @staticmethod
    def _looks_like_resource_limit(text: str) -> bool:
        return any(token in text for token in ("资源", "次数", "消耗", "额度", "限制", "冷却", "代价"))

    @staticmethod
    def _looks_like_authority_boundary(text: str) -> bool:
        return any(token in text for token in ("权限", "禁地", "组织", "资格", "许可", "边界", "宗门", "官府"))

    def evaluate(
        self,
        *,
        branch_id: str,
        chapter_index: int,
        artifact_payload: dict[str, object],
        facts: list[FactRecord],
    ) -> CheckerResult:
        start = perf_counter()
        risk_items: list[GateRiskItem] = []
        notes: list[str] = []
        status = "ready"
        common = RiskSemanticSignalService.common_signals(artifact_payload)
        scope = RiskSemanticSignalService.setting_scope_signals(artifact_payload, facts)
        observed_rules = scope.observed_world_rules
        constraining_rules = scope.constraining_world_rules
        rule_facts = scope.rule_facts
        merged_scope = scope.merged_scope
        unsupported = common.unsupported
        ambiguous = common.ambiguous
        transition_notes = common.transition_notes
        unresolved_threads = common.unresolved_threads
        custom_issues = cast(list[object], artifact_payload.get("setting_scope_issues", []))
        for item in custom_issues:
            if not isinstance(item, dict):
                continue
            summary = str(item.get("summary") or "").strip()
            if not summary:
                continue
            risk_items.append(
                GateRiskItem(
                    checker_name=self.name,
                    risk_domain=self.domain,
                    risk_type=str(item.get("risk_type") or "setting_scope_review_candidate"),
                    severity=str(item.get("severity") or "medium"),
                    confidence=float(item.get("confidence") or 0.55),
                    summary=summary,
                    supporting_evidence=self._rank_supporting_evidence(
                        [str(x).strip() for x in cast(list[object], item.get("supporting_evidence", [])) if str(x).strip()],
                        subtype=str(item.get("risk_type") or "setting_scope_review_candidate"),
                    ),
                    counter_evidence=_dedupe_texts(
                        [str(x).strip() for x in cast(list[object], item.get("counter_evidence", [])) if str(x).strip()]
                    ),
                    related_entities=_dedupe_texts(
                        [str(x).strip() for x in cast(list[object], item.get("related_entities", [])) if str(x).strip()]
                    ),
                    related_chapters=[chapter_index],
                    needs_human_review=bool(item.get("needs_human_review", True)),
                    risk_key=_risk_key(branch_id, chapter_index, self.name, summary[:80]),
                )
            )

        if not risk_items:
            derived_supporting: list[str] = []
            derived_counter: list[str] = []
            derived_type = "setting_scope_review_candidate"
            derived_summary = "本章存在设定作用域/边界信号，建议做一致性人工复核。"

            if constraining_rules and unsupported and any(self._looks_like_scope_expansion(text) for text in unsupported + transition_notes):
                derived_supporting = (
                    constraining_rules[:1]
                    + [text for text in unsupported + transition_notes if self._looks_like_scope_expansion(text)][:1]
                )[:2]
                if self.retrieval_search is not None and constraining_rules:
                    try:
                        pack = self.retrieval_search(
                            branch_id=branch_id,
                            chapter_index=chapter_index,
                            query_text=constraining_rules[0],
                            signal_type='rule_scope',
                            limit=2,
                        )
                        derived_supporting = (
                            derived_supporting
                            + pack.support_texts
                            + pack.exact_hints
                            + [f"object:{item.object_type}:{item.label}" for item in pack.latest_objects]
                        )[:5]
                    except Exception:
                        pass
                derived_counter = ["当前也可能只是例外通道或临时开放，仍需结合前后文确认适用范围是否真的扩大。"]
                derived_type = "constraint_scope_expansion"
                derived_summary = "本章设定适用范围疑似被异常放大，建议人工复核。"
            elif constraining_rules and unsupported and any(self._looks_like_resource_limit(text) for text in unsupported):
                derived_supporting = (
                    constraining_rules[:1]
                    + [text for text in unsupported if self._looks_like_resource_limit(text)][:1]
                )[:2]
                derived_counter = ["当前也可能只是暂未展示资源回收或消耗说明，仍需结合上下文复核。"]
                derived_type = "resource_limit_missing"
                derived_summary = "本章资源/次数/限制条件说明不足，建议人工复核。"
            elif constraining_rules and unsupported and any(self._looks_like_authority_boundary(text) for text in unsupported + transition_notes):
                derived_supporting = (
                    constraining_rules[:1]
                    + [text for text in unsupported + transition_notes if self._looks_like_authority_boundary(text)][:1]
                )[:2]
                derived_counter = ["当前也可能是特批、临时授权或身份变化所致，仍需结合正文复核。"]
                derived_type = "authority_boundary_conflict"
                derived_summary = "本章权限/组织/地理边界出现可疑突破，建议人工复核。"
            elif merged_scope and unsupported:
                derived_supporting = (merged_scope[:1] + unsupported[:1])[:2]
                derived_counter = ["当前设定范围结论与正文支撑之间仍可能存在解释空间。"]
                derived_type = "setting_scope_support_gap"
                derived_summary = "本章设定作用域/边界存在支撑缺口，建议人工复核。"
            elif merged_scope and ambiguous:
                derived_supporting = (merged_scope[:1] + ambiguous[:1])[:2]
                derived_counter = ["当前更像设定边界表述含混，尚不足以直接确认作用域异常。"]
                derived_type = "setting_scope_ambiguity_candidate"
                derived_summary = "本章设定作用域/边界表述存在歧义，建议人工复核。"
            elif merged_scope and unresolved_threads:
                derived_supporting = (merged_scope[:1] + unresolved_threads[:1])[:2]
                derived_counter = ["当前更像设定边界未闭合线程，而不是已确认异常。"]
                derived_type = "setting_scope_open_thread_candidate"
                derived_summary = "本章存在未闭合的设定作用域/边界线程，建议人工复核。"
            elif merged_scope:
                derived_supporting = merged_scope[:2]
                derived_counter = ["当前缺少稳定的跨章节边界冲突证据，先保持提示级别。"]

            if artifact_payload.get("needs_human_review") and derived_supporting:
                risk_items.append(
                    GateRiskItem(
                        checker_name=self.name,
                        risk_domain=self.domain,
                        risk_type=derived_type,
                        severity="low",
                        confidence=0.3,
                        summary=derived_summary,
                        supporting_evidence=self._rank_supporting_evidence(derived_supporting, subtype=derived_type)[:3],
                        counter_evidence=derived_counter,
                        related_entities=[],
                        related_chapters=[chapter_index],
                        needs_human_review=True,
                        risk_key=_risk_key(branch_id, chapter_index, self.name, derived_type),
                    )
                )
                status = "partial"
                notes.append("检测到弱设定作用域/边界信号，已结合 state_summary / artifact 证据约束降级为人工复核候选。")
            else:
                status = "skipped"
                notes.append("缺少足够的设定作用域/边界信号，当前跳过设定范围风险生成。")
        elif custom_issues and not merged_scope:
            status = "partial"
            notes.append("当前主要依赖 artifact hint 生成设定作用域风险，尚未建立稳定边界真源。")

        return CheckerResult(
            checker_name=self.name,
            chapter_index=chapter_index,
            status=status,
            risks=risk_items,
            notes=notes,
            latency_ms=int((perf_counter() - start) * 1000),
        )


@dataclass(slots=True)
class ThreadClosureConsistencyChecker:
    """Phase-2 thread-closure checker for dropped/escalated/conflict-closing stability."""

    name: str = "thread_closure_consistency"
    domain: str = "thread_closure"
    retrieval_search: object | None = None

    @staticmethod
    def _rank_supporting_evidence(items: list[str], *, subtype: str) -> list[str]:
        def score(text: str) -> tuple[int, int]:
            keywords = {
                "thread_dropped_after_escalation": ["冲突", "升级", "断头", "未提", "线程"],
                "closure_without_resolution_basis": ["已解决", "收束", "结束", "依据", "证据"],
                "ending_stability_candidate": ["结尾", "收束", "终局", "稳定", "回落"],
                "thread_closure_support_gap": ["冲突", "线程", "支撑", "依据"],
                "thread_closure_ambiguity_candidate": ["冲突", "线程", "歧义", "含混"],
                "thread_closure_open_thread_candidate": ["未解", "线程", "后续", "冲突"],
                "thread_closure_review_candidate": ["冲突", "收束", "线程", "结尾"],
            }.get(subtype, [])
            hit_count = sum(1 for keyword in keywords if keyword in text)
            return (hit_count, len(text))

        deduped = _dedupe_texts(items)
        return sorted(deduped, key=lambda text: score(text), reverse=True)

    @staticmethod
    def _artifact_conflict_signals(artifact_payload: dict[str, object]) -> tuple[list[str], list[str]]:
        state_summary = cast(dict[str, object], artifact_payload.get("state_summary", {}))
        new_conflicts = [
            str(x).strip()
            for x in cast(list[object], state_summary.get("new_conflicts", []))
            if str(x).strip()
        ]
        escalated_conflicts = [
            str(x).strip()
            for x in cast(list[object], state_summary.get("escalated_conflicts", []))
            if str(x).strip()
        ]
        return new_conflicts, escalated_conflicts

    def evaluate(
        self,
        *,
        branch_id: str,
        chapter_index: int,
        artifact_payload: dict[str, object],
        facts: list[FactRecord],
    ) -> CheckerResult:
        start = perf_counter()
        risk_items: list[GateRiskItem] = []
        notes: list[str] = []
        status = "ready"
        common = RiskSemanticSignalService.common_signals(artifact_payload)
        closure = RiskSemanticSignalService.thread_closure_signals(artifact_payload, facts)
        new_conflicts = closure.new_conflicts
        escalated_conflicts = closure.escalated_conflicts
        conflict_facts = closure.conflict_facts
        merged_conflicts = closure.merged_conflicts
        unsupported = common.unsupported
        ambiguous = common.ambiguous
        resolutions = common.resolutions
        unresolved_threads = common.unresolved_threads
        custom_issues = cast(list[object], artifact_payload.get("thread_closure_issues", []))
        for item in custom_issues:
            if not isinstance(item, dict):
                continue
            summary = str(item.get("summary") or "").strip()
            if not summary:
                continue
            risk_items.append(
                GateRiskItem(
                    checker_name=self.name,
                    risk_domain=self.domain,
                    risk_type=str(item.get("risk_type") or "thread_closure_review_candidate"),
                    severity=str(item.get("severity") or "medium"),
                    confidence=float(item.get("confidence") or 0.55),
                    summary=summary,
                    supporting_evidence=self._rank_supporting_evidence(
                        [str(x).strip() for x in cast(list[object], item.get("supporting_evidence", [])) if str(x).strip()],
                        subtype=str(item.get("risk_type") or "thread_closure_review_candidate"),
                    ),
                    counter_evidence=_dedupe_texts(
                        [str(x).strip() for x in cast(list[object], item.get("counter_evidence", [])) if str(x).strip()]
                    ),
                    related_entities=_dedupe_texts(
                        [str(x).strip() for x in cast(list[object], item.get("related_entities", [])) if str(x).strip()]
                    ),
                    related_chapters=[chapter_index],
                    needs_human_review=bool(item.get("needs_human_review", True)),
                    risk_key=_risk_key(branch_id, chapter_index, self.name, summary[:80]),
                )
            )

        if not risk_items:
            derived_supporting: list[str] = []
            derived_counter: list[str] = []
            derived_type = "thread_closure_review_candidate"
            derived_summary = "本章存在冲突线程/收束信号，建议做一致性人工复核。"

            if escalated_conflicts and unresolved_threads and not resolutions:
                derived_supporting = (escalated_conflicts[:1] + unresolved_threads[:1])[:2]
                if self.retrieval_search is not None and escalated_conflicts:
                    try:
                        pack = self.retrieval_search(
                            branch_id=branch_id,
                            chapter_index=chapter_index,
                            query_text=escalated_conflicts[0],
                            signal_type='conflict_thread',
                            limit=2,
                        )
                        derived_supporting = (
                            derived_supporting
                            + pack.support_texts
                            + pack.state_summaries
                            + pack.exact_hints
                            + [f"object:{item.object_type}:{item.label}" for item in pack.latest_objects]
                        )[:5]
                    except Exception:
                        pass
                derived_counter = ["当前也可能只是阶段性按下不表，仍需结合后续章节确认是否真的断头。"]
                derived_type = "thread_dropped_after_escalation"
                derived_summary = "本章冲突已升级但后续承接不足，存在线程断头候选，建议人工复核。"
            elif escalated_conflicts and resolutions and unsupported:
                derived_supporting = (escalated_conflicts[:1] + resolutions[:1] + unsupported[:1])[:3]
                derived_counter = ["当前也可能只是阶段性缓和，而非真正完成收束，仍需结合后文复核。"]
                derived_type = "closure_without_resolution_basis"
                derived_summary = "本章出现收束/解决表述，但缺少足够解决依据，建议人工复核。"
            elif new_conflicts and resolutions and ambiguous:
                derived_supporting = (new_conflicts[:1] + resolutions[:1] + ambiguous[:1])[:3]
                derived_counter = ["当前也可能是小阶段结尾，不一定构成长跨度收束异常。"]
                derived_type = "ending_stability_candidate"
                derived_summary = "本章收束稳定性存在可疑点，建议人工复核。"
            elif merged_conflicts and unsupported:
                derived_supporting = (merged_conflicts[:1] + unsupported[:1])[:2]
                derived_counter = ["当前冲突收束结论与正文支撑之间仍可能存在解释空间。"]
                derived_type = "thread_closure_support_gap"
                derived_summary = "本章冲突线程/收束存在支撑缺口，建议人工复核。"
            elif merged_conflicts and ambiguous:
                derived_supporting = (merged_conflicts[:1] + ambiguous[:1])[:2]
                derived_counter = ["当前更像线程收束表述含混，尚不足以直接确认异常。"]
                derived_type = "thread_closure_ambiguity_candidate"
                derived_summary = "本章冲突线程/收束表述存在歧义，建议人工复核。"
            elif merged_conflicts and unresolved_threads:
                derived_supporting = (merged_conflicts[:1] + unresolved_threads[:1])[:2]
                derived_counter = ["当前更像未闭合冲突线程，而不是已确认收束异常。"]
                derived_type = "thread_closure_open_thread_candidate"
                derived_summary = "本章存在未闭合的冲突线程/收束问题，建议人工复核。"
            elif merged_conflicts:
                derived_supporting = merged_conflicts[:2]
                derived_counter = ["当前缺少稳定的跨章节冲突收束证据，先保持提示级别。"]

            if artifact_payload.get("needs_human_review") and derived_supporting:
                risk_items.append(
                    GateRiskItem(
                        checker_name=self.name,
                        risk_domain=self.domain,
                        risk_type=derived_type,
                        severity="low",
                        confidence=0.3,
                        summary=derived_summary,
                        supporting_evidence=self._rank_supporting_evidence(derived_supporting, subtype=derived_type)[:3],
                        counter_evidence=derived_counter,
                        related_entities=[],
                        related_chapters=[chapter_index],
                        needs_human_review=True,
                        risk_key=_risk_key(branch_id, chapter_index, self.name, derived_type),
                    )
                )
                status = "partial"
                notes.append("检测到弱冲突线程/收束信号，已结合 state_summary / artifact 证据约束降级为人工复核候选。")
            else:
                status = "skipped"
                notes.append("缺少足够的冲突线程/收束信号，当前跳过线程收束风险生成。")
        elif custom_issues and not merged_conflicts:
            status = "partial"
            notes.append("当前主要依赖 artifact hint 生成线程收束风险，尚未建立稳定冲突生命周期真源。")

        return CheckerResult(
            checker_name=self.name,
            chapter_index=chapter_index,
            status=status,
            risks=risk_items,
            notes=notes,
            latency_ms=int((perf_counter() - start) * 1000),
        )


@dataclass(slots=True)
class PlotLogicChecker:
    """Phase-1 plot/causality checker with strong advisory-only downgrade semantics."""

    name: str = "plot_logic_consistency"
    domain: str = "plot"

    @staticmethod
    def _rank_supporting_evidence(items: list[str], *, subtype: str) -> list[str]:
        def score(text: str) -> tuple[int, int]:
            keywords = {
                "causality_break": ["因果", "前置", "结果", "行动"],
                "motivation_to_action_gap": ["动机", "决定", "行动", "选择", "前置"],
                "thread_state_conflict": ["已解决", "未解", "线程", "冲突", "反转"],
                "logic_review_candidate": ["逻辑", "因果", "支撑", "解释"],
                "resolution_support_gap": ["解决", "兑现", "解除", "完成"],
                "transition_support_gap": ["推进", "转向", "变化", "结果"],
                "unresolved_causality_candidate": ["未解", "未解释", "线程", "后续"],
            }.get(subtype, [])
            hit_count = sum(1 for keyword in keywords if keyword in text)
            return (hit_count, len(text))

        deduped = _dedupe_texts(items)
        return sorted(deduped, key=lambda text: score(text), reverse=True)

    @staticmethod
    def _looks_like_motivation_signal(text: str) -> bool:
        return any(token in text for token in ("动机", "决定", "选择", "态度", "立场"))

    @staticmethod
    def _looks_like_action_signal(text: str) -> bool:
        return any(token in text for token in ("行动", "出手", "执行", "推进", "结果"))

    @classmethod
    def _structured_plot_signals(
        cls,
        unsupported: list[str],
        transition_notes: list[str],
        resolutions: list[str],
        unresolved_threads: list[str],
    ) -> tuple[dict[str, list[str]], list[str]]:
        grouped: dict[str, list[str]] = {
            "motivation_like": [],
            "action_like": [],
            "resolved_like": [],
            "unresolved_like": [],
        }
        for text in unsupported:
            if cls._looks_like_motivation_signal(text):
                grouped["motivation_like"].append(text)
            if cls._looks_like_action_signal(text):
                grouped["action_like"].append(text)
        for text in transition_notes:
            if cls._looks_like_action_signal(text):
                grouped["action_like"].append(text)
        for text in resolutions:
            grouped["resolved_like"].append(text)
        for text in unresolved_threads:
            grouped["unresolved_like"].append(text)
        summary_bits = [key for key, values in grouped.items() if values]
        return grouped, summary_bits

    def evaluate(
        self,
        *,
        branch_id: str,
        chapter_index: int,
        artifact_payload: dict[str, object],
        facts: list[FactRecord],
    ) -> CheckerResult:
        start = perf_counter()
        risk_items: list[GateRiskItem] = []
        notes: list[str] = []
        status = "ready"
        custom_issues = cast(list[object], artifact_payload.get("plot_logic_issues", []))
        common = RiskSemanticSignalService.common_signals(artifact_payload)
        plot = RiskSemanticSignalService.plot_signals(artifact_payload)
        unsupported = common.unsupported
        ambiguous = common.ambiguous
        transition_notes = common.transition_notes
        resolutions = common.resolutions
        unresolved_threads = common.unresolved_threads
        structured_signals, structured_signal_bits = plot.structured_signals, plot.structured_signal_bits
        for item in custom_issues:
            if not isinstance(item, dict):
                continue
            summary = str(item.get("summary") or "").strip()
            if not summary:
                continue
            risk_items.append(
                GateRiskItem(
                    checker_name=self.name,
                    risk_domain=self.domain,
                    risk_type=str(item.get("risk_type") or "causality_break"),
                    severity=str(item.get("severity") or "medium"),
                    confidence=float(item.get("confidence") or 0.55),
                    summary=summary,
                    supporting_evidence=self._rank_supporting_evidence([
                        str(x).strip()
                        for x in cast(list[object], item.get("supporting_evidence", []))
                        if str(x).strip()
                    ], subtype=str(item.get("risk_type") or "causality_break")),
                    counter_evidence=[
                        str(x).strip()
                        for x in cast(list[object], item.get("counter_evidence", []))
                        if str(x).strip()
                    ],
                    related_entities=[
                        str(x).strip()
                        for x in cast(list[object], item.get("related_entities", []))
                        if str(x).strip()
                    ],
                    related_chapters=[chapter_index],
                    needs_human_review=bool(item.get("needs_human_review", True)),
                    risk_key=_risk_key(branch_id, chapter_index, self.name, summary[:80]),
                )
            )

        if not risk_items:
            derived_supporting: list[str] = []
            derived_counter: list[str] = []
            derived_type = "logic_review_candidate"
            derived_summary = "本章存在因果/剧情逻辑上的可疑点，建议人工复核。"
            if unsupported and resolutions and unresolved_threads and not transition_notes:
                derived_supporting = (resolutions[:1] + unresolved_threads[:1] + unsupported[:1])[:3]
                derived_counter = ["当前也可能是阶段性解决而非真正闭环，仍需结合后续章节复核。"]
                derived_type = "thread_state_conflict"
                derived_summary = "本章同时出现已解决与未解线程信号，线程状态存在冲突候选，建议人工复核。"
            elif unsupported and structured_signals["motivation_like"] and structured_signals["action_like"]:
                derived_supporting = (
                    structured_signals["motivation_like"][:1] + structured_signals["action_like"][:1]
                )[:2]
                derived_counter = ["当前也可能是动机信息前置于其他章节，仍需结合上下文复核。"]
                derived_type = "motivation_to_action_gap"
                derived_summary = "本章动机到行动的因果桥不足，建议人工复核。"
            elif unsupported and resolutions:
                derived_supporting = (unsupported[:1] + resolutions[:1])[:2]
                derived_counter = ["当前已出现解决性表述，但其证据链可能仍不完整。"]
                derived_type = "resolution_support_gap"
                derived_summary = "本章存在“已解决/已兑现”类表述，但支撑链条可能不足，建议人工复核。"
            elif unsupported and transition_notes:
                derived_supporting = (unsupported[:1] + transition_notes[:1])[:2]
                derived_counter = ["当前推进说明与证据约束之间仍可能存在解释空间。"]
                derived_type = "transition_support_gap"
                derived_summary = "本章推进结论与证据支撑之间存在可疑缺口，建议人工复核。"
            elif ambiguous and unresolved_threads:
                derived_supporting = (ambiguous[:1] + unresolved_threads[:1])[:2]
                derived_counter = ["当前更像未完全闭合的剧情线程，而不是可直接确认的逻辑错误。"]
                derived_type = "unresolved_causality_candidate"
                derived_summary = "本章存在未闭合的因果/剧情线程，建议人工复核。"
            elif unsupported or ambiguous:
                derived_supporting = (unsupported[:2] + ambiguous[:2])[:2]
                derived_counter = ["当前缺少稳定的事件因果真源，先保持提示级别。"]

            if artifact_payload.get("needs_human_review") and derived_supporting:
                derived_supporting = self._rank_supporting_evidence(derived_supporting, subtype=derived_type)[:3]
                risk_items.append(
                    GateRiskItem(
                        checker_name=self.name,
                        risk_domain=self.domain,
                        risk_type=derived_type,
                        severity="low",
                        confidence=0.3,
                        summary=derived_summary,
                        supporting_evidence=derived_supporting,
                        counter_evidence=derived_counter,
                        related_entities=[],
                        related_chapters=[chapter_index],
                        needs_human_review=True,
                        risk_key=_risk_key(branch_id, chapter_index, self.name, derived_type),
                    )
                )
                status = "partial"
                notes.append("检测到弱因果/逻辑信号，已结合 artifact 推进/解决/未解字段降级为人工复核候选。")
                if structured_signal_bits:
                    notes.append(f"plot structured signals={','.join(structured_signal_bits)}")
            else:
                status = "skipped"
                notes.append("缺少足够的因果/剧情逻辑信号，当前跳过逻辑风险生成。")
        elif custom_issues and not (unsupported or ambiguous):
            status = "partial"
            notes.append("当前主要依赖 artifact hint 生成剧情逻辑风险，尚未建立稳定事件因果真源。")

        return CheckerResult(
            checker_name=self.name,
            chapter_index=chapter_index,
            status=status,
            risks=risk_items,
            notes=notes,
            latency_ms=int((perf_counter() - start) * 1000),
        )


@dataclass(slots=True)
class TimelineConsistencyChecker:
    """Phase-1 timeline checker with explicit signal-precondition semantics."""

    name: str = "timeline_consistency"
    domain: str = "timeline"
    retrieval_search: object | None = None

    @staticmethod
    def _rank_supporting_evidence(items: list[str], *, subtype: str) -> list[str]:
        def score(text: str) -> tuple[int, int]:
            keywords = {
                "timeline_conflict": ["时间", "先后", "同日", "恢复", "顺序"],
                "sequence_conflict_candidate": ["当夜", "次日", "翌日", "同日", "顺序"],
                "recovery_window_insufficient": ["恢复", "三日后", "次日", "当夜", "时长"],
                "timeline_support_gap": ["时间", "顺序", "恢复", "证据", "支撑"],
                "timeline_ambiguity_candidate": ["歧义", "含混", "暂时", "压缩"],
                "timeline_transition_candidate": ["推进", "转入", "再出现", "回返"],
                "timeline_open_thread_candidate": ["未解释", "未解", "线程", "恢复"],
                "timeline_review_candidate": ["时间", "顺序", "恢复", "同日"],
            }.get(subtype, [])
            hit_count = sum(1 for keyword in keywords if keyword in text)
            return (hit_count, len(text))

        deduped = _dedupe_texts(items)
        return sorted(deduped, key=lambda text: score(text), reverse=True)

    @staticmethod
    def _timeline_anchor_bucket(text: str) -> str | None:
        same_day_tokens = ("当夜", "同夜", "当日", "同日", "当天", "当晚")
        next_day_tokens = ("次日", "翌日", "第二天")
        multi_day_tokens = ("三日后", "数日后", "几日后", "半月后", "一月后", "数月后", "半年后", "一周后")
        if any(token in text for token in same_day_tokens):
            return "same_day"
        if any(token in text for token in next_day_tokens):
            return "next_day"
        if any(token in text for token in multi_day_tokens):
            return "multi_day"
        return None

    @classmethod
    def _structured_timeline_signals(
        cls,
        timeline_signals: list[str],
        unsupported: list[str],
    ) -> tuple[dict[str, list[str]], list[str]]:
        grouped: dict[str, list[str]] = {
            "same_day": [],
            "next_day": [],
            "multi_day": [],
            "recovery_related": [],
        }
        for text in timeline_signals:
            bucket = cls._timeline_anchor_bucket(text)
            if bucket is not None:
                grouped[bucket].append(text)
            if any(token in text for token in ("恢复", "痊愈", "闭关", "赶路", "回城", "再出现")):
                grouped["recovery_related"].append(text)
        for text in unsupported:
            if any(token in text for token in ("恢复", "痊愈", "时长", "赶路", "回城")):
                grouped["recovery_related"].append(text)
        summary_bits = [key for key, values in grouped.items() if values]
        return grouped, summary_bits

    @staticmethod
    def _looks_like_recovery_gap(text: str) -> bool:
        return any(token in text for token in ("恢复", "痊愈", "伤势", "时长", "调息", "赶路", "回城"))

    def evaluate(
        self,
        *,
        branch_id: str,
        chapter_index: int,
        artifact_payload: dict[str, object],
        facts: list[FactRecord],
    ) -> CheckerResult:
        start = perf_counter()
        risk_items: list[GateRiskItem] = []
        notes: list[str] = []
        status = "ready"
        custom_issues = cast(list[object], artifact_payload.get("timeline_issues", []))
        common = RiskSemanticSignalService.common_signals(artifact_payload)
        timeline = RiskSemanticSignalService.timeline_signals(artifact_payload)
        timeline_signals = timeline.timeline_signals
        unsupported = common.unsupported
        ambiguous = common.ambiguous
        transition_notes = common.transition_notes
        unresolved_threads = common.unresolved_threads
        structured_signals, structured_signal_bits = timeline.structured_signals, timeline.structured_signal_bits
        for item in custom_issues:
            if not isinstance(item, dict):
                continue
            summary = str(item.get("summary") or "").strip()
            if not summary:
                continue
            risk_items.append(
                GateRiskItem(
                    checker_name=self.name,
                    risk_domain=self.domain,
                    risk_type=str(item.get("risk_type") or "timeline_conflict"),
                    severity=str(item.get("severity") or "medium"),
                    confidence=float(item.get("confidence") or 0.55),
                    summary=summary,
                    supporting_evidence=self._rank_supporting_evidence([
                        str(x).strip()
                        for x in cast(list[object], item.get("supporting_evidence", []))
                        if str(x).strip()
                    ], subtype=str(item.get("risk_type") or "timeline_conflict")),
                    counter_evidence=[
                        str(x).strip()
                        for x in cast(list[object], item.get("counter_evidence", []))
                        if str(x).strip()
                    ],
                    related_entities=[
                        str(x).strip()
                        for x in cast(list[object], item.get("related_entities", []))
                        if str(x).strip()
                    ],
                    related_chapters=[chapter_index],
                    needs_human_review=bool(item.get("needs_human_review", True)),
                    risk_key=_risk_key(branch_id, chapter_index, self.name, summary[:80]),
                )
            )

        if not risk_items:
            derived_supporting: list[str] = []
            derived_counter: list[str] = []
            derived_type = "timeline_review_candidate"
            derived_summary = "本章存在时间线/顺序信号，建议做一致性人工复核。"
            has_recovery_gap = any(self._looks_like_recovery_gap(text) for text in unsupported)
            has_short_window_mix = bool(structured_signals["same_day"] or structured_signals["next_day"]) and bool(
                structured_signals["multi_day"]
            )
            if (
                timeline_signals
                and unsupported
                and has_recovery_gap
                and has_short_window_mix
                and not transition_notes
                and not ambiguous
            ):
                derived_supporting = (
                    structured_signals["same_day"][:1]
                    + structured_signals["multi_day"][:1]
                    + [text for text in unsupported if self._looks_like_recovery_gap(text)][:1]
                )[:3]
                derived_counter = ["当前也可能是叙事压缩或省略了中间恢复过程，仍需结合前后文复核。"]
                derived_type = "recovery_window_insufficient"
                derived_summary = "本章恢复/赶路窗口与时间锚点之间存在时长不足候选，建议人工复核。"
            elif (
                timeline_signals
                and structured_signals["same_day"]
                and structured_signals["next_day"]
                and not unsupported
            ):
                derived_supporting = (
                    structured_signals["same_day"][:1] + structured_signals["next_day"][:1]
                )[:2]
                derived_counter = ["当前也可能是章节切换压缩了叙事顺序，仍需结合前后文复核。"]
                derived_type = "sequence_conflict_candidate"
                derived_summary = "本章出现同日/次日并置的顺序冲突候选，建议人工复核。"
            elif timeline_signals and unsupported:
                derived_supporting = (timeline_signals[:1] + unsupported[:1])[:2]
                if self.retrieval_search is not None and timeline_signals:
                    try:
                        pack = self.retrieval_search(
                            branch_id=branch_id,
                            chapter_index=chapter_index,
                            query_text=timeline_signals[0],
                            signal_type='timeline_anchor',
                            limit=2,
                        )
                        derived_supporting = (
                            derived_supporting
                            + pack.support_texts
                            + pack.state_summaries
                            + pack.exact_hints
                            + [f"object:{item.object_type}:{item.label}" for item in pack.latest_objects]
                        )[:5]
                    except Exception:
                        pass
                derived_counter = ["当前时间顺序结论与证据约束之间仍可能存在解释空间。"]
                derived_type = "timeline_support_gap"
                derived_summary = "本章时间顺序/恢复节奏存在支撑缺口，建议人工复核。"
            elif (
                timeline_signals
                and structured_signals["same_day"]
                and structured_signals["next_day"]
            ):
                derived_supporting = (
                    structured_signals["same_day"][:1] + structured_signals["next_day"][:1]
                )[:2]
                derived_counter = ["当前也可能是章节切换压缩了叙事顺序，仍需结合前后文复核。"]
                derived_type = "sequence_conflict_candidate"
                derived_summary = "本章出现同日/次日并置的顺序冲突候选，建议人工复核。"
            elif timeline_signals and ambiguous:
                derived_supporting = (timeline_signals[:1] + ambiguous[:1])[:2]
                derived_counter = ["当前更像时间表述压缩或省略，尚不足以直接确认时间线冲突。"]
                derived_type = "timeline_ambiguity_candidate"
                derived_summary = "本章时间线表述存在歧义，建议人工复核。"
            elif timeline_signals and transition_notes:
                derived_supporting = (timeline_signals[:1] + transition_notes[:1])[:2]
                derived_counter = ["当前推进说明与时间顺序之间可能仍有合理解释。"]
                derived_type = "timeline_transition_candidate"
                derived_summary = "本章状态推进与时间顺序之间存在可疑点，建议人工复核。"
            elif timeline_signals and unresolved_threads:
                derived_supporting = (timeline_signals[:1] + unresolved_threads[:1])[:2]
                derived_counter = ["当前更像尚未闭合的时序线程，而不是已确认冲突。"]
                derived_type = "timeline_open_thread_candidate"
                derived_summary = "本章存在未闭合的时序线程，建议人工复核。"
            elif timeline_signals:
                derived_supporting = timeline_signals[:2]
                derived_counter = ["当前缺少稳定时间线冲突证据，先保持提示级别。"]

            if artifact_payload.get("needs_human_review") and derived_supporting:
                derived_supporting = self._rank_supporting_evidence(derived_supporting, subtype=derived_type)[:3]
                risk_items.append(
                    GateRiskItem(
                        checker_name=self.name,
                        risk_domain=self.domain,
                        risk_type=derived_type,
                        severity="low",
                        confidence=0.28,
                        summary=derived_summary,
                        supporting_evidence=derived_supporting,
                        counter_evidence=derived_counter,
                        related_entities=[],
                        related_chapters=[chapter_index],
                        needs_human_review=True,
                        risk_key=_risk_key(branch_id, chapter_index, self.name, derived_type),
                    )
                )
                status = "partial"
                notes.append("检测到弱时间线信号，已结合 artifact 推进/未解/证据约束字段降级为人工复核候选。")
                if structured_signal_bits:
                    notes.append(f"timeline structured signals={','.join(structured_signal_bits)}")
            else:
                status = "skipped"
                notes.append("缺少足够的时间线信号，当前跳过时间线风险生成。")
        elif custom_issues and not timeline_signals:
            status = "partial"
            notes.append("当前主要依赖 artifact hint 生成时间线风险，尚未建立稳定时间线真源。")

        return CheckerResult(
            checker_name=self.name,
            chapter_index=chapter_index,
            status=status,
            risks=risk_items,
            notes=notes,
            latency_ms=int((perf_counter() - start) * 1000),
        )


@dataclass(slots=True)
class PowerScalingChecker:
    """Phase-1 power/capability drift checker with explicit downgrade behavior."""

    name: str = "power_scaling_consistency"
    domain: str = "power"
    retrieval_search: object | None = None

    @staticmethod
    def _rank_supporting_evidence(items: list[str], *, subtype: str) -> list[str]:
        def score(text: str) -> tuple[int, int]:
            keywords = {
                "capability_shift": ["能力", "实力", "越阶", "压制", "招式"],
                "upset_without_setup": ["越阶", "压制", "反杀", "跨级", "铺垫"],
                "cost_constraint_missing": ["代价", "限制", "消耗", "冷却", "负担"],
                "power_support_gap": ["能力", "实力", "越阶", "证据", "支撑"],
                "power_ambiguity_candidate": ["歧义", "含混", "暂时", "一次性"],
                "power_transition_candidate": ["推进", "跃迁", "转攻", "压制"],
                "power_open_thread_candidate": ["未解释", "未解", "线程", "来源"],
                "power_review_candidate": ["能力", "实力", "越阶", "压制"],
            }.get(subtype, [])
            hit_count = sum(1 for keyword in keywords if keyword in text)
            return (hit_count, len(text))

        deduped = _dedupe_texts(items)
        return sorted(deduped, key=lambda text: score(text), reverse=True)

    @staticmethod
    def _looks_like_upset_signal(text: str) -> bool:
        return any(token in text for token in ("越阶", "跨级", "压制", "反杀", "碾压"))

    @staticmethod
    def _looks_like_cost_signal(text: str) -> bool:
        return any(token in text for token in ("代价", "限制", "消耗", "冷却", "负担", "后遗症"))

    @classmethod
    def _structured_power_signals(
        cls,
        power_signals: list[str],
        unsupported: list[str],
    ) -> tuple[dict[str, list[str]], list[str]]:
        grouped: dict[str, list[str]] = {
            "upset_like": [],
            "new_capability": [],
            "cost_constraint": [],
        }
        for text in power_signals:
            if cls._looks_like_upset_signal(text):
                grouped["upset_like"].append(text)
            if any(token in text for token in ("新招式", "新能力", "突破", "掌握", "跃迁")):
                grouped["new_capability"].append(text)
            if cls._looks_like_cost_signal(text):
                grouped["cost_constraint"].append(text)
        for text in unsupported:
            if cls._looks_like_cost_signal(text):
                grouped["cost_constraint"].append(text)
        summary_bits = [key for key, values in grouped.items() if values]
        return grouped, summary_bits

    def evaluate(
        self,
        *,
        branch_id: str,
        chapter_index: int,
        artifact_payload: dict[str, object],
        facts: list[FactRecord],
    ) -> CheckerResult:
        start = perf_counter()
        risk_items: list[GateRiskItem] = []
        notes: list[str] = []
        status = "ready"
        custom_issues = cast(list[object], artifact_payload.get("power_scaling_issues", []))
        common = RiskSemanticSignalService.common_signals(artifact_payload)
        power = RiskSemanticSignalService.power_signals(artifact_payload)
        power_signals = power.power_signals
        unsupported = common.unsupported
        ambiguous = common.ambiguous
        transition_notes = common.transition_notes
        unresolved_threads = common.unresolved_threads
        structured_signals, structured_signal_bits = power.structured_signals, power.structured_signal_bits
        for item in custom_issues:
            if not isinstance(item, dict):
                continue
            summary = str(item.get("summary") or "").strip()
            if not summary:
                continue
            risk_items.append(
                GateRiskItem(
                    checker_name=self.name,
                    risk_domain=self.domain,
                    risk_type=str(item.get("risk_type") or "capability_shift"),
                    severity=str(item.get("severity") or "medium"),
                    confidence=float(item.get("confidence") or 0.55),
                    summary=summary,
                    supporting_evidence=self._rank_supporting_evidence([
                        str(x).strip()
                        for x in cast(list[object], item.get("supporting_evidence", []))
                        if str(x).strip()
                    ], subtype=str(item.get("risk_type") or "capability_shift")),
                    counter_evidence=[
                        str(x).strip()
                        for x in cast(list[object], item.get("counter_evidence", []))
                        if str(x).strip()
                    ],
                    related_entities=[
                        str(x).strip()
                        for x in cast(list[object], item.get("related_entities", []))
                        if str(x).strip()
                    ],
                    related_chapters=[chapter_index],
                    needs_human_review=bool(item.get("needs_human_review", True)),
                    risk_key=_risk_key(branch_id, chapter_index, self.name, summary[:80]),
                )
            )

        if not risk_items:
            derived_supporting: list[str] = []
            derived_counter: list[str] = []
            derived_type = "power_review_candidate"
            derived_summary = "本章存在战力/能力变化信号，建议做一致性人工复核。"
            if (
                power_signals
                and structured_signals["upset_like"]
                and structured_signals["new_capability"]
                and not unsupported
            ):
                derived_supporting = (
                    structured_signals["upset_like"][:1] + structured_signals["new_capability"][:1]
                )[:2]
                derived_counter = ["当前也可能是对手轻敌、属性克制或一次性加成所致，仍需结合上下文复核。"]
                derived_type = "upset_without_setup"
                derived_summary = "本章出现越阶/压制结果，但前置铺垫不足，建议人工复核。"
            elif power_signals and unsupported and structured_signals["upset_like"] and any(
                self._looks_like_cost_signal(text) for text in unsupported
            ):
                derived_supporting = (
                    structured_signals["upset_like"][:1]
                    + [text for text in unsupported if self._looks_like_cost_signal(text)][:1]
                )[:2]
                derived_counter = ["当前也可能只是暂未展示代价回收或冷却说明，仍需结合前后文复核。"]
                derived_type = "cost_constraint_missing"
                derived_summary = "本章强力表现后的代价/限制说明不足，建议人工复核。"
            elif power_signals and unsupported:
                derived_supporting = (power_signals[:1] + unsupported[:1])[:2]
                if self.retrieval_search is not None and power_signals:
                    try:
                        pack = self.retrieval_search(
                            branch_id=branch_id,
                            chapter_index=chapter_index,
                            query_text=power_signals[0],
                            signal_type='power_state',
                            limit=2,
                        )
                        derived_supporting = (
                            derived_supporting
                            + pack.support_texts
                            + pack.state_summaries
                            + pack.exact_hints
                            + [f"object:{item.object_type}:{item.label}" for item in pack.latest_objects]
                        )[:5]
                    except Exception:
                        pass
                derived_counter = ["当前战力结论与证据约束之间仍可能存在解释空间。"]
                derived_type = "power_support_gap"
                derived_summary = "本章战力/能力变化存在支撑缺口，建议人工复核。"
            elif power_signals and ambiguous:
                derived_supporting = (power_signals[:1] + ambiguous[:1])[:2]
                derived_counter = ["当前更像能力表述含混，尚不足以直接确认战力漂移。"]
                derived_type = "power_ambiguity_candidate"
                derived_summary = "本章战力/能力表述存在歧义，建议人工复核。"
            elif power_signals and transition_notes:
                derived_supporting = (power_signals[:1] + transition_notes[:1])[:2]
                derived_counter = ["当前状态推进与能力跃迁之间可能仍有合理解释。"]
                derived_type = "power_transition_candidate"
                derived_summary = "本章状态推进与能力跃迁之间存在可疑点，建议人工复核。"
            elif power_signals and unresolved_threads:
                derived_supporting = (power_signals[:1] + unresolved_threads[:1])[:2]
                derived_counter = ["当前更像尚未闭合的战力线程，而不是已确认能力冲突。"]
                derived_type = "power_open_thread_candidate"
                derived_summary = "本章存在未闭合的战力/能力线程，建议人工复核。"
            elif power_signals:
                derived_supporting = power_signals[:2]
                derived_counter = ["当前缺少稳定战力基线与冲突证据，先保持提示级别。"]

            if artifact_payload.get("needs_human_review") and derived_supporting:
                derived_supporting = self._rank_supporting_evidence(derived_supporting, subtype=derived_type)[:2]
                risk_items.append(
                    GateRiskItem(
                        checker_name=self.name,
                        risk_domain=self.domain,
                        risk_type=derived_type,
                        severity="low",
                        confidence=0.28,
                        summary=derived_summary,
                        supporting_evidence=derived_supporting,
                        counter_evidence=derived_counter,
                        related_entities=[],
                        related_chapters=[chapter_index],
                        needs_human_review=True,
                        risk_key=_risk_key(branch_id, chapter_index, self.name, derived_type),
                    )
                )
                status = "partial"
                notes.append("检测到弱战力/能力信号，已结合 artifact 推进/未解/证据约束字段降级为人工复核候选。")
                if structured_signal_bits:
                    notes.append(f"power structured signals={','.join(structured_signal_bits)}")
            else:
                status = "skipped"
                notes.append("缺少足够的战力/能力信号，当前跳过战力风险生成。")
        elif custom_issues and not power_signals:
            status = "partial"
            notes.append("当前主要依赖 artifact hint 生成战力风险，尚未建立稳定战力真源。")

        return CheckerResult(
            checker_name=self.name,
            chapter_index=chapter_index,
            status=status,
            risks=risk_items,
            notes=notes,
            latency_ms=int((perf_counter() - start) * 1000),
        )


class RiskAuditService:
    """Persist checker results and aggregate a unified chapter risk card."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.risk_signal_store = RiskSignalStoreService(session)
        self.risk_signal_link = RiskSignalLinkService(session)
        self.risk_signal_cluster = RiskSignalClusterService(session)
        self.risk_evidence_pack = RiskEvidencePackService(
            session,
            self.risk_signal_store,
            self.risk_signal_link,
            self.risk_signal_cluster,
        )
        self.semantic_signal_lookup: dict[tuple[str, int], list[object]] = {}
        self.checkers: list[GateChecker] = [
            CharacterOOCChecker(),
            WorldRuleConsistencyChecker(),
            RelationshipConsistencyChecker(),
            ForeshadowPayoffChecker(),
            SettingScopeConsistencyChecker(),
            ThreadClosureConsistencyChecker(),
            PlotLogicChecker(),
            TimelineConsistencyChecker(),
            PowerScalingChecker(),
        ]
        for checker in self.checkers:
            if getattr(checker, "name", "") == "foreshadow_payoff_consistency":
                checker.retrieval_search = self.risk_evidence_pack.build_pack  # type: ignore[attr-defined]
            if getattr(checker, "name", "") == "relationship_consistency":
                checker.retrieval_search = self.risk_evidence_pack.build_pack  # type: ignore[attr-defined]
            if getattr(checker, "name", "") == "setting_scope_consistency":
                checker.retrieval_search = self.risk_evidence_pack.build_pack  # type: ignore[attr-defined]
            if getattr(checker, "name", "") == "thread_closure_consistency":
                checker.retrieval_search = self.risk_evidence_pack.build_pack  # type: ignore[attr-defined]
            if getattr(checker, "name", "") == "timeline_consistency":
                checker.retrieval_search = self.risk_evidence_pack.build_pack  # type: ignore[attr-defined]
            if getattr(checker, "name", "") == "power_scaling_consistency":
                checker.retrieval_search = self.risk_evidence_pack.build_pack  # type: ignore[attr-defined]

    @staticmethod
    def _is_missing_relation_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return "relation" in message and "does not exist" in message

    def _artifact_payload(self, branch_id: str, chapter_index: int) -> dict[str, object]:
        artifact = self.session.scalar(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.chapter_index == chapter_index)
            .where(ChapterArtifact.visibility == "active")
            .order_by(ChapterArtifact.created_at.desc())
        )
        if artifact is None:
            raise ValueError("chapter artifact not found")
        return cast(dict[str, object], artifact.payload_json)

    def _facts(self, branch_id: str, chapter_index: int) -> list[FactRecord]:
        return list(
            self.session.scalars(
                select(FactRecord)
                .where(FactRecord.branch_id == branch_id)
                .where(FactRecord.chapter_index == chapter_index)
                .order_by(FactRecord.fact_type, FactRecord.label)
            ).all()
        )

    def _replace_checker_result(self, branch_id: str, chapter_index: int, result: CheckerResult) -> GateCheckerResultRecord:
        self.session.execute(
            update(GateCheckerResultRecord)
            .where(GateCheckerResultRecord.branch_id == branch_id)
            .where(GateCheckerResultRecord.chapter_index == chapter_index)
            .where(GateCheckerResultRecord.checker_name == result.checker_name)
            .where(GateCheckerResultRecord.visibility == "active")
            .values(visibility="hidden")
        )
        record = GateCheckerResultRecord(
            branch_id=branch_id,
            chapter_index=chapter_index,
            checker_name=result.checker_name,
            payload_json=result.model_dump(mode="json"),
            status=result.status,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def _replace_risk_card(self, card: ChapterRiskCard) -> ChapterRiskCardRecord:
        self.session.execute(
            update(ChapterRiskCardRecord)
            .where(ChapterRiskCardRecord.branch_id == card.branch_id)
            .where(ChapterRiskCardRecord.chapter_index == card.chapter_index)
            .where(ChapterRiskCardRecord.visibility == "active")
            .values(visibility="hidden")
        )
        record = ChapterRiskCardRecord(
            branch_id=card.branch_id,
            chapter_index=card.chapter_index,
            payload_json=card.model_dump(mode="json"),
            status="ready" if not card.coverage_gaps else "partial",
        )
        self.session.add(record)
        self.session.flush()
        return record

    @staticmethod
    def aggregate(
        *,
        branch_id: str,
        chapter_index: int,
        checker_results: Sequence[CheckerResult],
    ) -> ChapterRiskCard:
        deduped: dict[str, GateRiskItem] = {}
        checker_statuses: dict[str, str] = {}
        coverage_gaps: list[str] = []
        for result in checker_results:
            checker_statuses[result.checker_name] = result.status
            if result.status in {"partial", "failed", "skipped"}:
                coverage_gaps.append(f"{result.checker_name}:{result.status}")
            for risk in result.risks:
                existing = deduped.get(risk.risk_key)
                if existing is None:
                    deduped[risk.risk_key] = risk
                    continue
                existing.supporting_evidence = _dedupe_texts(
                    existing.supporting_evidence + risk.supporting_evidence
                )
                existing.counter_evidence = _dedupe_texts(
                    existing.counter_evidence + risk.counter_evidence
                )
                existing.related_entities = _dedupe_texts(
                    existing.related_entities + risk.related_entities
                )
                existing.related_chapters = sorted(set(existing.related_chapters + risk.related_chapters))
                existing.confidence = max(existing.confidence, risk.confidence)
                severity_rank = {"low": 0, "medium": 1, "high": 2}
                if severity_rank.get(risk.severity, 0) > severity_rank.get(existing.severity, 0):
                    existing.severity = risk.severity
                if len(risk.summary) > len(existing.summary):
                    existing.summary = risk.summary
        all_risks = list(deduped.values())

        severity_counts = Counter(risk.severity for risk in all_risks)
        domain_counts = Counter(risk.risk_domain for risk in all_risks)
        top_risks = sorted(
            all_risks,
            key=lambda item: (
                {"high": 0, "medium": 1, "low": 2}.get(item.severity, 3),
                -item.confidence,
                item.risk_key,
            ),
        )[:8]
        overall = "low"
        if severity_counts.get("high"):
            overall = "high"
        elif severity_counts.get("medium"):
            overall = "medium"
        elif coverage_gaps and not all_risks:
            overall = "low"

        return ChapterRiskCard(
            branch_id=branch_id,
            chapter_index=chapter_index,
            overall_risk_level=overall,
            top_risks=top_risks,
            risk_counts_by_domain=dict(domain_counts),
            risk_counts_by_severity=dict(severity_counts),
            review_status="pending",
            generated_at=datetime.now(UTC).isoformat(),
            checker_statuses=checker_statuses,
            coverage_gaps=coverage_gaps,
        )

    def generate_for_chapter(self, branch_id: str, chapter_index: int) -> ChapterRiskCard:
        artifact_payload = self._artifact_payload(branch_id, chapter_index)
        facts = self._facts(branch_id, chapter_index)
        results: list[CheckerResult] = []
        for checker in self.checkers:
            try:
                result = checker.evaluate(
                    branch_id=branch_id,
                    chapter_index=chapter_index,
                    artifact_payload=artifact_payload,
                    facts=facts,
                )
            except Exception as exc:  # noqa: BLE001
                result = CheckerResult(
                    checker_name=checker.name,
                    chapter_index=chapter_index,
                    status="failed",
                    risks=[],
                    notes=[f"{checker.name} failed: {exc}"],
                    latency_ms=None,
                )
            self._replace_checker_result(branch_id, chapter_index, result)
            results.append(result)
        stored_signals = self.risk_signal_store.replace_branch_chapter_signals(
            branch_id=branch_id,
            chapter_index=chapter_index,
            items=RiskSignalStoreService.build_signal_items(
                artifact_payload=artifact_payload,
                checker_results=[result.model_dump(mode="json") for result in results],
            ),
        )
        self.semantic_signal_lookup[(branch_id, chapter_index)] = stored_signals
        self.risk_signal_link.replace_branch_links(
            branch_id=branch_id,
            chapter_index=chapter_index,
            items=self.risk_signal_link.build_minimal_link_proposals(
                branch_id=branch_id,
                chapter_index=chapter_index,
                signals=[
                    {
                        "id": signal.id,
                        "signal_type": signal.signal_type,
                        "raw_text": signal.raw_text,
                        "canonical_label": signal.canonical_label,
                        "confidence": signal.confidence,
                    }
                    for signal in stored_signals
                ],
            ),
        )
        self.risk_signal_cluster.replace_branch_chapter_clusters(
            branch_id=branch_id,
            chapter_index=chapter_index,
            clusters=self.risk_signal_cluster.build_clusters_from_signals(
                branch_id=branch_id,
                chapter_index=chapter_index,
            ),
        )
        card = self.aggregate(branch_id=branch_id, chapter_index=chapter_index, checker_results=results)
        self._replace_risk_card(card)
        self.session.commit()
        return card

    def load_risk_card(self, branch_id: str, chapter_index: int) -> dict[str, object] | None:
        record = self.session.scalar(
            select(ChapterRiskCardRecord)
            .where(ChapterRiskCardRecord.branch_id == branch_id)
            .where(ChapterRiskCardRecord.chapter_index == chapter_index)
            .where(ChapterRiskCardRecord.visibility == "active")
            .order_by(ChapterRiskCardRecord.created_at.desc())
        )
        return cast(dict[str, object], record.payload_json) if record is not None else None

    def load_risk_summary(self, run_id: str, branch_id: str) -> dict[str, object]:
        export_bundle = ExportService(self.session).export_branch_bundle(run_id, branch_id)
        chapter_rows = cast(list[dict[str, object]], export_bundle.get("chapter_index", []))
        try:
            cards = list(
                self.session.scalars(
                    select(ChapterRiskCardRecord)
                    .where(ChapterRiskCardRecord.branch_id == branch_id)
                    .where(ChapterRiskCardRecord.visibility == "active")
                    .order_by(ChapterRiskCardRecord.chapter_index)
                ).all()
            )
        except ProgrammingError as exc:
            if not self._is_missing_relation_error(exc):
                raise
            self.session.rollback()
            return {
                "chapter_count": len(chapter_rows),
                "risk_card_count": 0,
                "checker_result_count": 0,
                "high_risk_chapters": [],
                "risk_counts_by_severity": {},
                "risk_counts_by_domain": {},
            }
        risk_cards = [cast(dict[str, object], record.payload_json) for record in cards]
        severity_counts: Counter[str] = Counter()
        domain_counts: Counter[str] = Counter()
        high_risk_chapters: list[int] = []
        for card in risk_cards:
            severity_counts.update(cast(dict[str, int], card.get("risk_counts_by_severity", {})))
            domain_counts.update(cast(dict[str, int], card.get("risk_counts_by_domain", {})))
            if str(card.get("overall_risk_level")) == "high":
                high_risk_chapters.append(int(card.get("chapter_index", 0)))
        return {
            "chapter_count": len(chapter_rows),
            "risk_card_count": len(risk_cards),
            "high_risk_chapters": high_risk_chapters,
            "risk_counts_by_severity": dict(severity_counts),
            "risk_counts_by_domain": dict(domain_counts),
        }
