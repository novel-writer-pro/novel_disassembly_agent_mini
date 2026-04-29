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
from novel_analyzer.services.export_service import ExportService


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
        fact_character_signals = [
            fact.label for fact in facts if fact.fact_type in {"character_motivation", "character_relation", "character_belief"}
        ]
        unsupported = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("unsupported_inferences", []))
            if str(x).strip()
        ]
        ambiguous = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("ambiguous_points", []))
            if str(x).strip()
        ]
        transition_notes = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("state_transition_notes", []))
            if str(x).strip()
        ]
        resolutions = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("evidence_backed_resolutions", []))
            if str(x).strip()
        ]
        unresolved_threads = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("unresolved_threads", []))
            if str(x).strip()
        ]
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
        rule_signals = [
            fact.label for fact in facts if fact.fact_type == "world_rule"
        ]
        artifact_rule_signals = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("world_rule_signals", []))
            if str(x).strip()
        ]
        unsupported = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("unsupported_inferences", []))
            if str(x).strip()
        ]
        ambiguous = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("ambiguous_points", []))
            if str(x).strip()
        ]
        resolutions = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("evidence_backed_resolutions", []))
            if str(x).strip()
        ]
        unresolved_threads = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("unresolved_threads", []))
            if str(x).strip()
        ]
        merged_rule_signals = _dedupe_texts(rule_signals + artifact_rule_signals)
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
class PlotLogicChecker:
    """Phase-1 plot/causality checker with strong advisory-only downgrade semantics."""

    name: str = "plot_logic_consistency"
    domain: str = "plot"

    @staticmethod
    def _rank_supporting_evidence(items: list[str], *, subtype: str) -> list[str]:
        def score(text: str) -> tuple[int, int]:
            keywords = {
                "causality_break": ["因果", "前置", "结果", "行动"],
                "logic_review_candidate": ["逻辑", "因果", "支撑", "解释"],
                "resolution_support_gap": ["解决", "兑现", "解除", "完成"],
                "transition_support_gap": ["推进", "转向", "变化", "结果"],
                "unresolved_causality_candidate": ["未解", "未解释", "线程", "后续"],
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
        custom_issues = cast(list[object], artifact_payload.get("plot_logic_issues", []))
        unsupported = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("unsupported_inferences", []))
            if str(x).strip()
        ]
        ambiguous = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("ambiguous_points", []))
            if str(x).strip()
        ]
        transition_notes = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("state_transition_notes", []))
            if str(x).strip()
        ]
        resolutions = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("evidence_backed_resolutions", []))
            if str(x).strip()
        ]
        unresolved_threads = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("unresolved_threads", []))
            if str(x).strip()
        ]
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
            if unsupported and resolutions:
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
                        related_entities=[],
                        related_chapters=[chapter_index],
                        needs_human_review=True,
                        risk_key=_risk_key(branch_id, chapter_index, self.name, derived_type),
                    )
                )
                status = "partial"
                notes.append("检测到弱因果/逻辑信号，已结合 artifact 推进/解决/未解字段降级为人工复核候选。")
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

    @staticmethod
    def _rank_supporting_evidence(items: list[str], *, subtype: str) -> list[str]:
        def score(text: str) -> tuple[int, int]:
            keywords = {
                "timeline_conflict": ["时间", "先后", "同日", "恢复", "顺序"],
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
        timeline_signals = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("timeline_signals", []))
            if str(x).strip()
        ]
        unsupported = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("unsupported_inferences", []))
            if str(x).strip()
        ]
        ambiguous = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("ambiguous_points", []))
            if str(x).strip()
        ]
        transition_notes = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("state_transition_notes", []))
            if str(x).strip()
        ]
        unresolved_threads = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("unresolved_threads", []))
            if str(x).strip()
        ]
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
            if timeline_signals and unsupported:
                derived_supporting = (timeline_signals[:1] + unsupported[:1])[:2]
                derived_counter = ["当前时间顺序结论与证据约束之间仍可能存在解释空间。"]
                derived_type = "timeline_support_gap"
                derived_summary = "本章时间顺序/恢复节奏存在支撑缺口，建议人工复核。"
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
                notes.append("检测到弱时间线信号，已结合 artifact 推进/未解/证据约束字段降级为人工复核候选。")
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

    @staticmethod
    def _rank_supporting_evidence(items: list[str], *, subtype: str) -> list[str]:
        def score(text: str) -> tuple[int, int]:
            keywords = {
                "capability_shift": ["能力", "实力", "越阶", "压制", "招式"],
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
        power_signals = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("power_signals", []))
            if str(x).strip()
        ]
        unsupported = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("unsupported_inferences", []))
            if str(x).strip()
        ]
        ambiguous = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("ambiguous_points", []))
            if str(x).strip()
        ]
        transition_notes = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("state_transition_notes", []))
            if str(x).strip()
        ]
        unresolved_threads = [
            str(x).strip()
            for x in cast(list[object], artifact_payload.get("unresolved_threads", []))
            if str(x).strip()
        ]
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
            if power_signals and unsupported:
                derived_supporting = (power_signals[:1] + unsupported[:1])[:2]
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
        self.checkers: list[GateChecker] = [
            CharacterOOCChecker(),
            WorldRuleConsistencyChecker(),
            PlotLogicChecker(),
            TimelineConsistencyChecker(),
            PowerScalingChecker(),
        ]

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
