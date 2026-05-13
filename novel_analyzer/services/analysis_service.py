"""Live chapter analysis service backed by the configured LLM."""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import re
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from langchain_core.messages import BaseMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.agent.pipeline import ChapterAgentContext, build_agent_stage_prompts
from novel_analyzer.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)
from novel_analyzer.database.models import (
    ChapterManifest,
    ChapterSegment,
    NovelSource,
    RunBranch,
)
from novel_analyzer.domain.analysis_dimensions import AnalysisDimension
from novel_analyzer.domain.schemas import (
    AntiFabricationGuardOutput,
    ChapterAnalysisLayerOutput,
    ChapterAnalysisOutput,
    ChapterFactExtractionOutput,
    ChapterIntakeOutput,
    DimensionResult,
    EvidenceBindingOutput,
    WriterLearningLensOutput,
)
from novel_analyzer.llm.client import build_chat_model
from novel_analyzer.llm.prompts import build_chapter_analysis_prompt
from novel_analyzer.runtime.provider_health import read_provider_health, record_provider_health
from novel_analyzer.services.auto_repair_service import AutoRepairService
from novel_analyzer.services.causal_graph_service import CausalGraphService
from novel_analyzer.services.claim_grounding_service import ClaimGroundingService
from novel_analyzer.services.confidence_calibration_service import ConfidenceCalibrationService
from novel_analyzer.services.context_service import ContextService
from novel_analyzer.services.domain_dictionary_service import DomainDictionaryService
from novel_analyzer.services.entity_resolution_service import EntityResolutionService
from novel_analyzer.services.fact_service import FactService
from novel_analyzer.services.foreshadowing_service import ForeshadowingService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.memory_consolidation_service import MemoryConsolidationService
from novel_analyzer.services.quality_gate_service import QualityGateService
from novel_analyzer.services.retrieval_service import RetrievalService
from novel_analyzer.services.risk_audit_service import RiskAuditService
from novel_analyzer.services.run_service import RunService
from novel_analyzer.services.self_evaluation_service import SelfEvaluationService


class AnalysisService:
    """Coordinates chapter content loading, skill-driven LLM analysis, and persistence."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.run_service = RunService(session, self.settings)
        self.retrieval_service = RetrievalService(session, self.settings)
        self.context_service = ContextService(session)
        self.fact_service = FactService(session)
        self.graph_service = GraphService(session)
        self.risk_audit_service = RiskAuditService(session)
        self.memory_consolidation = MemoryConsolidationService(session)
        self.foreshadowing_service = ForeshadowingService(session)
        self.entity_resolution = EntityResolutionService(session)
        self.causal_graph = CausalGraphService(session)
        self.confidence_calibration = ConfidenceCalibrationService(session)
        self.self_evaluation = SelfEvaluationService()
        self.domain_dictionary = DomainDictionaryService(session, self.settings)

    @staticmethod
    def _serialize_message_content(message: BaseMessage) -> str:
        """Normalize model content to plain text for persistence."""

        content = message.content
        if isinstance(content, list):
            return "\n".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        return str(content)

    @staticmethod
    def _stage_chapter_content(chapter_content: str, max_chars: int = 3600) -> str:
        """Trim oversized chapter text for small-model staged prompts while preserving
        head/tail context."""

        text = chapter_content.strip()
        if len(text) <= max_chars:
            return text
        head = text[:2200].rstrip()
        tail = text[-1200:].lstrip()
        omitted = len(text) - len(head) - len(tail)
        return f"{head}\n\n[... 中间内容已为阶段模型省略 {omitted} 字 ...]\n\n{tail}"

    @staticmethod
    def _score_chapter_complexity(
        intake: ChapterIntakeOutput,
        chapter_content: str,
    ) -> float:
        """Score chapter complexity (0-1) based on structural signals from intake.

        Factors: character count, scene switches, dialogue density, content length.
        High complexity chapters benefit from larger models.
        """
        char_count = len(chapter_content)
        scene_count = len(intake.scene_candidates)
        dialogue_count = len(intake.dialogue_candidates)
        paragraph_count = len(intake.paragraph_blocks)

        length_score = min(char_count / 5000.0, 1.0)
        scene_score = min(scene_count / 5.0, 1.0)
        dialogue_score = min(dialogue_count / 15.0, 1.0)
        density_score = min(paragraph_count / 20.0, 1.0)

        has_suspense = any(
            keyword in ' '.join(intake.notes)
            for keyword in ('悬念', '转场', '时间变化', '伏笔')
        ) if intake.notes else False
        suspense_bonus = 0.15 if has_suspense else 0.0

        return min(
            0.3 * length_score
            + 0.25 * scene_score
            + 0.2 * dialogue_score
            + 0.15 * density_score
            + 0.1 + suspense_bonus,
            1.0,
        )

    def _select_model_for_complexity(
        self,
        complexity_score: float,
        stage_model: object,
        fallback_model: object,
    ) -> object:
        """Route to fallback (larger) model when chapter complexity exceeds threshold."""
        if complexity_score >= 0.7:
            return fallback_model
        return stage_model

    @classmethod
    def _extract_json_payload(cls, message: BaseMessage) -> dict[str, object]:
        """Extract JSON content from a model response, tolerating fenced code blocks."""

        joined = cls._serialize_message_content(message)
        stripped = joined.strip()
        if stripped.startswith("```"):
            stripped = stripped.removeprefix("```json").removeprefix("```").strip()
            if stripped.endswith("```"):
                stripped = stripped[:-3].strip()

        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("model response does not contain a JSON object")
        candidate = stripped[start : end + 1]
        return cls._load_json_with_repair(candidate)

    @staticmethod
    def _load_json_with_repair(payload: str) -> dict[str, object]:
        """Load JSON with lightweight repair attempts for common LLM formatting drift."""

        def _attempt(text: str) -> dict[str, object] | None:
            try:
                loaded = json.loads(text)
            except json.JSONDecodeError:
                return None
            return cast(dict[str, object], loaded) if isinstance(loaded, dict) else None

        direct = _attempt(payload)
        if direct is not None:
            return direct

        candidates = [
            re.sub(r",(\s*[}\]])", r"\1", payload),
            payload.replace("“", '"').replace("”", '"').replace("’", "'"),
            re.sub(r"[\x00-\x1f]", "", payload),
        ]
        for text in candidates:
            repaired = _attempt(text)
            if repaired is not None:
                return repaired

        pythonish = (
            payload.replace("null", "None")
            .replace("true", "True")
            .replace("false", "False")
        )
        try:
            loaded = ast.literal_eval(pythonish)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("model response does not contain valid JSON after repair") from exc
        if not isinstance(loaded, dict):
            raise ValueError("repaired payload is not a JSON object")
        return cast(dict[str, object], loaded)

    def _invoke_with_retry(self, model: object, prompt: str) -> BaseMessage:
        health = read_provider_health(self.settings)
        if health.degraded_events >= 5 and health.last_status == 'degraded':
            logger.warning("provider degraded (%d events), pre-check passed but monitoring", health.degraded_events)

        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                result = cast(BaseMessage, model.invoke(prompt))  # type: ignore[attr-defined]
                record_provider_health(ok=True, settings=self.settings)
                return result
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                record_provider_health(ok=False, error_message=str(exc)[:200], settings=self.settings)
                if attempt == 3:
                    raise
                error_text = str(exc).lower()
                if '429' in error_text or 'rate limit' in error_text:
                    wait = float(attempt) * 5.0
                    logger.warning("rate limited (attempt %d/3), backing off %.1fs", attempt, wait)
                    time.sleep(wait)
                elif '503' in error_text or 'service temporarily unavailable' in error_text:
                    wait = float(attempt) * 3.0
                    logger.warning("provider 503 (attempt %d/3), backing off %.1fs", attempt, wait)
                    time.sleep(wait)
                else:
                    time.sleep(float(attempt))
        assert last_error is not None
        raise last_error

    def _invoke_stage(self, model: object, prompt: str, schema: type[object]) -> object:
        response = self._invoke_with_retry(model, prompt)
        raw = self._extract_json_payload(response)
        return schema.model_validate(raw)  # type: ignore[attr-defined]

    def _invoke_merged_stage(
        self,
        model: object,
        prompt: str,
        key_a: str,
        schema_a: type[object],
        key_b: str,
        schema_b: type[object],
    ) -> tuple[object, object]:
        """Invoke a merged prompt that returns {key_a: ..., key_b: ...} and parse both."""
        response = self._invoke_with_retry(model, prompt)
        raw = self._extract_json_payload(response)
        part_a = raw.get(key_a, {})
        part_b = raw.get(key_b, {})
        if not isinstance(part_a, dict):
            part_a = {}
        if not isinstance(part_b, dict):
            part_b = {}
        return (
            schema_a.model_validate(part_a),  # type: ignore[attr-defined]
            schema_b.model_validate(part_b),  # type: ignore[attr-defined]
        )

    @staticmethod
    def _should_skip_small_model_pipeline(job_attempts: int) -> bool:
        """Escalate repeated problem chapters directly to monolithic fallback."""

        return job_attempts >= 3

    @staticmethod
    def _labels_from_notes(notes: Sequence[object]) -> list[str]:
        labels: list[str] = []
        for item in notes:
            label = getattr(item, 'label', item)
            text = str(label).strip()
            if text:
                labels.append(text)
        return labels

    @staticmethod
    def _contains_transition_claim(text: str, keywords: list[str]) -> bool:
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _prompt_metrics(**prompts: str) -> dict[str, object]:
        char_counts = {f'{name}_chars': len(text) for name, text in prompts.items()}
        return {
            'prompt_char_counts': char_counts,
            'total_prompt_chars': sum(char_counts.values()),
        }

    @staticmethod
    def _compact_previous_summary(previous_summary: str, *, max_chars: int = 220) -> str:
        text = str(previous_summary or '').strip()
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 1].rstrip() + '…'

    def _select_few_shot_example(
        self,
        branch_id: str,
        chapter_index: int,
    ) -> str:
        """Select a compact prior chapter result as few-shot example for prompt injection."""
        if chapter_index <= 1:
            return ''
        target_ch = max(1, chapter_index - 1)
        from novel_analyzer.database.models import ChapterRawOutput
        raw = self.session.scalar(
            select(ChapterRawOutput)
            .where(ChapterRawOutput.branch_id == branch_id)
            .where(ChapterRawOutput.chapter_index == target_ch)
            .where(ChapterRawOutput.parse_status == 'parsed')
            .order_by(ChapterRawOutput.created_at.desc())
        )
        if raw is None or not raw.parsed_json:
            return ''
        parsed = raw.parsed_json
        if not isinstance(parsed, dict):
            return ''
        intake = parsed.get('intake', {})
        facts = parsed.get('facts', {})
        if not intake and not facts:
            return ''
        example = {}
        if intake and isinstance(intake, dict):
            example['intake'] = {
                'chapter_index': intake.get('chapter_index', target_ch),
                'normalized_title': str(intake.get('normalized_title', ''))[:30],
                'cleaned_text': str(intake.get('cleaned_text', ''))[:100] + '...',
                'paragraph_blocks': (intake.get('paragraph_blocks') or [])[:2],
                'dialogue_candidates': (intake.get('dialogue_candidates') or [])[:2],
                'scene_candidates': [],
                'notes': (intake.get('notes') or [])[:2],
            }
        if facts and isinstance(facts, dict):
            example['facts'] = {
                'characters': (facts.get('characters') or [])[:2],
                'events': (facts.get('events') or [])[:2],
                'relations': (facts.get('relations') or [])[:1],
                'conflicts': [],
                'foreshadowing': (facts.get('foreshadowing') or [])[:1],
                'worldbuilding_facts': [],
            }
        if not example:
            return ''
        compact = json.dumps(example, ensure_ascii=False)
        if len(compact) > 800:
            compact = compact[:800]
        return f'\n\n参考上一章的输出格式（仅供格式参考，内容请基于当前章节）：\n{compact}'

    @staticmethod
    def _compact_prior_context_json(
        prior_context: dict[str, object],
        *,
        max_facts: int = 12,
        high_confidence_threshold: float = 0.6,
    ) -> str:
        compact: dict[str, object] = {}
        facts = prior_context.get('facts')
        if isinstance(facts, list) and facts:
            sorted_facts = sorted(
                [f for f in facts if isinstance(f, dict)],
                key=lambda f: (-float(f.get('confidence', 0)), -int(f.get('chapter_index', 0))),
            )
            compact_facts: list[dict[str, object]] = []
            for item in sorted_facts[:max_facts]:
                confidence = float(item.get('confidence', 0))
                if confidence >= high_confidence_threshold:
                    row: dict[str, object] = {}
                    for key in ('chapter_index', 'fact_type', 'label', 'confidence'):
                        value = item.get(key)
                        if value not in (None, '', []):
                            row[key] = value
                    if row:
                        compact_facts.append(row)
                else:
                    label = item.get('label')
                    if label:
                        compact_facts.append({'label': label, 'chapter_index': item.get('chapter_index')})
            if compact_facts:
                compact['facts'] = compact_facts
        foreshadow_threads = prior_context.get('open_foreshadowing_threads')
        if isinstance(foreshadow_threads, list) and foreshadow_threads:
            compact['open_foreshadowing'] = [
                {'label': t.get('label'), 'age': t.get('age')}
                for t in foreshadow_threads[:5]
                if isinstance(t, dict) and t.get('label')
            ]
        previous_summary = prior_context.get('previous_summary')
        if isinstance(previous_summary, str) and previous_summary.strip():
            compact['previous_summary'] = previous_summary.strip()[:200]
        return json.dumps(compact, ensure_ascii=False, indent=2) if compact else '{}'

    @staticmethod
    def _compact_state_summary_json(
        state_summary: dict[str, object],
        *,
        max_items: int = 3,
    ) -> str:
        compact: dict[str, object] = {}
        for key in (
            'paid_off_foreshadowing',
            'escalated_conflicts',
            'evolved_relations',
            'constraining_world_rules',
            'unresolved_threads',
        ):
            value = state_summary.get(key)
            if isinstance(value, list) and value:
                compact[key] = [str(item).strip() for item in value[:max_items] if str(item).strip()]
        return json.dumps(compact, ensure_ascii=False, indent=2) if compact else '{}'

    @classmethod
    def _derive_state_progression(
        cls,
        state_summary: dict[str, object],
        facts: ChapterFactExtractionOutput,
        analysis: ChapterAnalysisLayerOutput,
    ) -> tuple[list[str], list[str], list[str]]:
        """Derive chapter-level progression, resolution, and unresolved-thread notes."""

        fact_events = cls._labels_from_notes(facts.events)
        fact_relations = cls._labels_from_notes(facts.relations)
        fact_conflicts = cls._labels_from_notes(facts.conflicts)
        fact_foreshadowing = cls._labels_from_notes(facts.foreshadowing)
        transitions: list[str] = []
        resolutions: list[str] = []
        unresolved: list[str] = []

        if fact_events:
            transitions.append(f"本章状态推进集中体现在：{'、'.join(fact_events[:3])}。")
        if fact_relations:
            transitions.append(f"本章关系面出现可见变化：{'、'.join(fact_relations[:2])}。")
        if fact_conflicts:
            transitions.append(f"本章冲突面继续推进：{'、'.join(fact_conflicts[:2])}。")

        paid_off = state_summary.get('paid_off_foreshadowing', [])
        if isinstance(paid_off, list):
            for label in paid_off[:3]:
                text = str(label).strip()
                if text:
                    resolutions.append(f"前文伏笔“{text}”在当前分支中已有兑现信号。")

        evolved = state_summary.get('evolved_relations', [])
        if isinstance(evolved, list):
            for label in evolved[:2]:
                text = str(label).strip()
                if text:
                    resolutions.append(f"关系线“{text}”已出现阶段性变化证据。")

        for label in fact_foreshadowing[:3]:
            unresolved.append(f"新埋下的线程：{label}")
        escalated = state_summary.get('escalated_conflicts', [])
        if isinstance(escalated, list):
            for label in escalated[:3]:
                text = str(label).strip()
                if text:
                    unresolved.append(f"仍待后续处理的升级冲突：{text}")
        constraining = state_summary.get('constraining_world_rules', [])
        if isinstance(constraining, list):
            for label in constraining[:2]:
                text = str(label).strip()
                if text:
                    unresolved.append(f"持续施加约束的规则：{text}")

        for note in analysis.continuity_notes[:2]:
            text = str(note).strip()
            if text and text not in transitions:
                transitions.append(text)

        def dedup(items: list[str]) -> list[str]:
            return list(dict.fromkeys(item for item in items if item.strip()))

        return dedup(transitions), dedup(resolutions), dedup(unresolved)

    @classmethod
    def _state_summary_guard(
        cls,
        state_summary: dict[str, object],
        facts: ChapterFactExtractionOutput,
        analysis: ChapterAnalysisLayerOutput,
        guard: AntiFabricationGuardOutput,
    ) -> AntiFabricationGuardOutput:
        """Add deterministic no-fabrication warnings from prior state summary."""

        note_text = ' '.join(analysis.continuity_notes)
        fact_labels = set(
            cls._labels_from_notes(facts.events)
            + cls._labels_from_notes(facts.relations)
            + cls._labels_from_notes(facts.conflicts)
            + cls._labels_from_notes(facts.foreshadowing)
            + cls._labels_from_notes(facts.worldbuilding_facts)
        )
        overclaim_flags = list(guard.overclaim_flags)
        ambiguous_points = list(guard.ambiguous_points)

        paid_off = state_summary.get('paid_off_foreshadowing', [])
        if isinstance(paid_off, list) and cls._contains_transition_claim(
            note_text,
            ['回收', '兑现'],
        ):
            if not fact_labels:
                overclaim_flags.append('前情伏笔被宣称回收/兑现，但本章事实层缺少对应支撑。')

        escalated = state_summary.get('escalated_conflicts', [])
        if isinstance(escalated, list) and cls._contains_transition_claim(
            note_text,
            ['解决', '化解', '终止'],
        ):
            current_conflicts = cls._labels_from_notes(facts.conflicts)
            if not current_conflicts:
                overclaim_flags.append('前情升级冲突被宣称解决/终止，但本章未提供新的冲突事实支撑。')

        evolved_relations = state_summary.get('evolved_relations', [])
        if isinstance(evolved_relations, list) and cls._contains_transition_claim(
            note_text,
            ['关系变化', '和解', '反目', '修复'],
        ):
            current_relations = cls._labels_from_notes(facts.relations)
            if not current_relations:
                ambiguous_points.append('关系状态出现解释性变化表述，但事实层缺少关系证据。')

        constraining_rules = state_summary.get('constraining_world_rules', [])
        if isinstance(constraining_rules, list) and cls._contains_transition_claim(
            note_text,
            ['规则改变', '限制解除', '不再受限'],
        ):
            current_rules = cls._labels_from_notes(facts.worldbuilding_facts)
            if not current_rules:
                overclaim_flags.append('规则/约束被宣称改变或解除，但本章缺少世界规则事实支撑。')

        needs_review = guard.needs_human_review or bool(overclaim_flags)
        return guard.model_copy(
            update={
                'overclaim_flags': overclaim_flags,
                'ambiguous_points': ambiguous_points,
                'needs_human_review': needs_review,
            }
        )


    def _invoke_monolithic_analysis(
        self,
        model: object,
        chapter_index: int,
        normalized_title: str,
        chapter_content: str,
    ) -> ChapterAnalysisOutput:
        prompt = build_chapter_analysis_prompt(
            chapter_index=chapter_index,
            normalized_title=normalized_title,
            chapter_content=chapter_content,
        )
        response = self._invoke_with_retry(model, prompt)
        raw = self._extract_json_payload(response)
        return ChapterAnalysisOutput.model_validate(raw)

    @staticmethod
    def _is_provider_unavailable_error(exc: Exception) -> bool:
        text = str(exc)
        markers = [
            "Insufficient Balance",
            "SUBSCRIPTION_NOT_FOUND",
            "Your request was blocked",
            "Error code: 402",
            "Error code: 403",
        ]
        return any(marker in text for marker in markers)

    @staticmethod
    def _heuristic_entities(chapter_content: str, limit: int = 5) -> list[str]:
        candidates = re.findall(r"[一-龥]{2,4}", chapter_content)
        stop_words = {
            "第章", "求收藏", "求追读", "本章完", "说道", "一个", "两个",
            "没有", "可以", "自己", "什么", "这样",
        }
        seen: set[str] = set()
        results: list[str] = []
        for item in candidates:
            if item in stop_words or item in seen:
                continue
            seen.add(item)
            results.append(item)
            if len(results) >= limit:
                break
        return results

    @classmethod
    def _build_local_heuristic_analysis(
        cls,
        chapter_index: int,
        normalized_title: str,
        chapter_content: str,
    ) -> ChapterAnalysisOutput:
        content = chapter_content.strip()
        summary_source = re.split(r"[。！？\n]", content, maxsplit=1)[0].strip()
        chapter_summary = (
            summary_source[:120]
            if summary_source
            else f"本章围绕《{normalized_title}》展开。"
        )
        key_entities = cls._heuristic_entities(content)
        key_events = [chapter_summary] if chapter_summary else []
        continuity_notes = [
            "当前章节因上游 provider 不可用，使用本地启发式分析保底生成。",
            "建议后续在 provider 恢复后对该章补做完整 LLM 分析。",
        ]
        writer_learning_notes = [
            "当前为保底分析结果，重点先保证章节不断档，再在后续补足风格与细节层判断。"
        ]
        quality_gate_notes = [
            "provider unavailable -> local heuristic fallback"
        ]
        return ChapterAnalysisOutput(
            chapter_index=chapter_index,
            normalized_title=normalized_title,
            dimensions=[],
            chapter_summary=chapter_summary,
            key_entities=key_entities,
            key_events=key_events,
            continuity_notes=continuity_notes,
            writer_learning_notes=writer_learning_notes,
            unsupported_inferences=[],
            ambiguous_points=["启发式保底输出，细粒度事实与风格判断有限。"],
            needs_human_review=True,
            quality_gate_notes=quality_gate_notes,
            hook_score=2.5,
            state_transition_notes=[],
            evidence_backed_resolutions=[],
            unresolved_threads=[],
        )

    @staticmethod
    def _is_sparse_result(result: ChapterAnalysisOutput) -> bool:
        return (
            not result.chapter_summary.strip()
            and not result.key_entities
            and not result.key_events
            and not result.continuity_notes
        )

    @staticmethod
    def _content_hash(chapter_content: str) -> str:
        return hashlib.sha256(chapter_content.encode('utf-8')).hexdigest()

    @classmethod
    def _build_deconstruction_profile(
        cls,
        *,
        chapter_content: str,
        stage_payload: dict[str, object],
        writer_deferred: bool,
    ) -> dict[str, Any]:
        fallback = str(stage_payload.get('fallback') or '').strip()
        stage_error = str(stage_payload.get('stage_error') or '').strip()
        profile = 'quick'
        writer_lens_status = 'deferred' if writer_deferred else 'complete'
        timing = {
            'commit_phase': 'sync',
            'enrichment_phase': 'deferred' if writer_deferred else 'inline',
        }
        if fallback:
            timing['fallback_mode'] = fallback
        if stage_error:
            timing['stage_error'] = stage_error
        return {
            'profile': profile,
            'quick_ready': True,
            'writer_lens_status': writer_lens_status,
            'loom_status': 'pending',
            'risk_status': 'pending',
            'canonical_artifact_id': None,
            'content_hash': cls._content_hash(chapter_content),
            'idempotency_key': None,
            'timing': timing,
        }

    @staticmethod
    def _with_deconstruction_profile(
        payload: dict[str, Any],
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        enriched = dict(payload)
        enriched['_deconstruction_profile'] = profile
        return enriched

    @staticmethod
    def _merge_stage_outputs(
        chapter_index: int,
        normalized_title: str,
        facts: ChapterFactExtractionOutput,
        analysis: ChapterAnalysisLayerOutput,
        writer: WriterLearningLensOutput,
        guard: AntiFabricationGuardOutput,
        state_transition_notes: list[str] | None = None,
        evidence_backed_resolutions: list[str] | None = None,
        unresolved_threads: list[str] | None = None,
    ) -> ChapterAnalysisOutput:
        dimensions: list[DimensionResult] = []
        for item in facts.worldbuilding_facts:
            dimensions.append(
                DimensionResult(
                    dimension=AnalysisDimension.WORLDBUILDING,
                    summary=item.label,
                    evidence=item.evidence,
                    confidence=item.confidence,
                )
            )
        for item in facts.foreshadowing:
            dimensions.append(
                DimensionResult(
                    dimension=AnalysisDimension.FORESHADOWING,
                    summary=item.label,
                    evidence=item.evidence,
                    confidence=item.confidence,
                )
            )
        for item in facts.conflicts:
            dimensions.append(
                DimensionResult(
                    dimension=AnalysisDimension.CONFLICTS,
                    summary=item.label,
                    evidence=item.evidence,
                    confidence=item.confidence,
                )
            )
        for item in analysis.themes:
            dimensions.append(
                DimensionResult(
                    dimension=AnalysisDimension.THEMES,
                    summary=item.label,
                    evidence=item.evidence,
                    confidence=item.confidence,
                )
            )
        if analysis.pacing:
            dimensions.append(
                DimensionResult(
                    dimension=AnalysisDimension.PACING,
                    summary="; ".join(f"{key}: {value}" for key, value in analysis.pacing.items()),
                    evidence=[],
                    confidence=0.7,
                )
            )
        if analysis.emotional_curve:
            dimensions.append(
                DimensionResult(
                    dimension=AnalysisDimension.EMOTIONAL_CURVE,
                    summary=(
                        "; ".join(
                            f"{key}: {value}" for key, value in analysis.emotional_curve.items()
                        )
                    ),
                    evidence=[],
                    confidence=0.7,
                )
            )

        writer_notes = (
            writer.transferable_lessons
            + writer.hook_notes
            + writer.conflict_notes
            + writer.reveal_order_notes
            + writer.scene_efficiency_notes
        )
        return ChapterAnalysisOutput(
            chapter_index=chapter_index,
            normalized_title=normalized_title,
            dimensions=dimensions,
            chapter_summary=analysis.summary.compact(),
            key_entities=[item.label for item in facts.characters],
            key_events=[item.label for item in facts.events],
            continuity_notes=analysis.continuity_notes,
            state_transition_notes=state_transition_notes or [],
            evidence_backed_resolutions=evidence_backed_resolutions or [],
            unresolved_threads=unresolved_threads or [],
            writer_learning_notes=writer_notes,
            unsupported_inferences=guard.unsupported_inferences + guard.overclaim_flags,
            ambiguous_points=guard.ambiguous_points,
            needs_human_review=guard.needs_human_review,
        )

    def _update_foreshadowing_lifecycle(
        self,
        branch_id: str,
        chapter_index: int,
        stage_payload: dict[str, object],
        state_summary: dict[str, object],
    ) -> None:
        facts_data = stage_payload.get('facts', {})
        if not isinstance(facts_data, dict):
            return
        foreshadowing_list = facts_data.get('foreshadowing', [])
        if not isinstance(foreshadowing_list, list):
            return
        foreshadowing_dicts = []
        for item in foreshadowing_list:
            if isinstance(item, dict):
                foreshadowing_dicts.append(item)
            elif hasattr(item, 'model_dump'):
                foreshadowing_dicts.append(item.model_dump())
        if foreshadowing_dicts or state_summary.get('paid_off_foreshadowing'):
            try:
                self.foreshadowing_service.update_from_facts(
                    branch_id, chapter_index, foreshadowing_dicts, state_summary,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("foreshadowing lifecycle update failed ch%d: %s", chapter_index, exc)

    def _update_causal_graph(
        self,
        branch_id: str,
        chapter_index: int,
        stage_payload: dict[str, object],
        state_summary: dict[str, object],
    ) -> None:
        facts_data = stage_payload.get('facts', {})
        if not isinstance(facts_data, dict):
            return
        try:
            links = self.causal_graph.extract_causal_links(
                chapter_index, facts_data, state_summary,
            )
            if links:
                self.causal_graph.materialize_causal_edges(
                    branch_id, chapter_index, links,
                )
            self.causal_graph.detect_logic_breaks(
                branch_id, chapter_index, facts_data,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("causal graph update failed ch%d: %s", chapter_index, exc)

    def analyze_range(
        self,
        run_id: str,
        branch_id: str,
        start_chapter: int,
        end_chapter: int,
    ) -> list[str]:
        """Analyze and persist a chapter range on a branch."""

        branch = self.session.scalar(select(RunBranch).where(RunBranch.id == branch_id))
        run, branch = self.run_service.get_run_and_branch(run_id, branch_id)

        manifest = self.session.scalar(
            select(ChapterManifest).where(ChapterManifest.id == run.manifest_id)
        )
        novel = self.session.scalar(select(NovelSource).where(NovelSource.id == run.novel_id))
        if manifest is None or novel is None:
            raise ValueError("run is missing manifest or novel source")

        full_text = Path(novel.source_path).read_text(encoding="utf-8")
        stage_model = build_chat_model(
            self.settings,
            model_name=self.settings.llm_stage_model_name,
        )
        fallback_model = build_chat_model(
            self.settings,
            model_name=self.settings.llm_fallback_model_name,
        )
        artifact_ids: list[str] = []
        previous_summary = ""

        segments = self.session.scalars(
            select(ChapterSegment)
            .where(ChapterSegment.manifest_id == manifest.id)
            .where(ChapterSegment.chapter_index >= start_chapter)
            .where(ChapterSegment.chapter_index <= end_chapter)
            .order_by(ChapterSegment.chapter_index)
        ).all()

        for segment in segments:
            job = self.run_service.start_chapter_job(branch_id, segment.chapter_index)
            response_text = ""
            raw_result: dict[str, object] | None = None
            stage_payload: dict[str, object] = {}
            prompt_metrics: dict[str, object] = {}
            try:
                self.run_service.update_job_progress(
                    branch_id,
                    segment.chapter_index,
                    current_stage='chapter_intake',
                    progress_percent=5,
                    emit_event=True,
                )
                chapter_content = full_text[segment.start_offset : segment.end_offset].strip()
                stage_chapter_content = self._stage_chapter_content(chapter_content)
                previous_summary = self._compact_previous_summary(
                    self.context_service.previous_summary(
                        branch_id,
                        segment.chapter_index,
                    )
                )
                prior_context = self.context_service.fact_context_json(
                    branch_id,
                    segment.chapter_index,
                )
                graph_context = self.context_service.graph_context_json(
                    branch_id,
                    segment.chapter_index,
                )
                state_summary = self.context_service.state_summary_json(
                    branch_id,
                    segment.chapter_index,
                )
                window_summary = self.context_service.window_summary(
                    branch_id,
                    segment.chapter_index,
                )
                prior_context_json = json.dumps(prior_context, ensure_ascii=False, indent=2)
                compact_prior_context_json = self._compact_prior_context_json(prior_context)
                graph_context_json = json.dumps(graph_context, ensure_ascii=False, indent=2)
                state_summary_json = json.dumps(state_summary, ensure_ascii=False, indent=2)
                try:
                    if self._should_skip_small_model_pipeline(job.attempts):
                        raise ValueError('skip staged pipeline after repeated retries')
                    self.run_service.update_job_progress(
                        branch_id,
                        segment.chapter_index,
                        current_stage='fact_extractor',
                        progress_percent=15,
                        emit_event=True,
                    )
                    prompts = build_agent_stage_prompts(
                        ChapterAgentContext(
                            chapter_index=segment.chapter_index,
                            normalized_title=segment.normalized_title,
                            chapter_content=stage_chapter_content,
                            previous_summary=previous_summary,
                            prior_context_json=prior_context_json,
                            graph_context_json=graph_context_json,
                            state_summary_json=state_summary_json,
                            window_summary=window_summary,
                        )
                    )
                    if self.settings.use_merged_stages:
                        try:
                            few_shot = self._select_few_shot_example(branch_id, segment.chapter_index)
                            merged_prompt = prompts['intake_and_facts']
                            if few_shot:
                                merged_prompt = merged_prompt + few_shot
                            intake, facts = self._invoke_merged_stage(
                                stage_model,
                                merged_prompt,
                                'intake', ChapterIntakeOutput,
                                'facts', ChapterFactExtractionOutput,
                            )
                            intake = cast(ChapterIntakeOutput, intake)
                            facts = cast(ChapterFactExtractionOutput, facts).ensure_minimum_facts(
                                intake.cleaned_text
                            )
                        except (ValueError, KeyError) as merge_exc:
                            logger.warning(
                                "merged intake+facts failed ch%d, falling back to separate stages: %s",
                                segment.chapter_index, merge_exc,
                            )
                            intake = cast(
                                ChapterIntakeOutput,
                                self._invoke_stage(
                                    stage_model,
                                    prompts['chapter_intake'],
                                    ChapterIntakeOutput,
                                ),
                            )
                    else:
                        intake = cast(
                            ChapterIntakeOutput,
                            self._invoke_stage(
                                stage_model,
                                prompts['chapter_intake'],
                                ChapterIntakeOutput,
                            ),
                        )
                    query_entities = self._heuristic_entities(
                        intake.cleaned_text or stage_chapter_content, limit=8
                    )
                    query_events = [
                        str(d).strip()
                        for d in intake.dialogue_candidates[:3]
                        if str(d).strip()
                    ]
                    complexity_score = self._score_chapter_complexity(
                        intake, stage_chapter_content,
                    )
                    active_model = self._select_model_for_complexity(
                        complexity_score, stage_model, fallback_model,
                    )
                    adaptive_prior = self.context_service.adaptive_fact_context_json(
                        branch_id, segment.chapter_index, query_entities, query_events,
                    )
                    adaptive_graph = self.context_service.adaptive_graph_context_json(
                        branch_id, segment.chapter_index, query_entities,
                    )
                    adaptive_prior_json = json.dumps(adaptive_prior, ensure_ascii=False, indent=2)
                    adaptive_graph_json = json.dumps(adaptive_graph, ensure_ascii=False, indent=2)
                    compact_state_summary_json = self._compact_state_summary_json(state_summary)
                    if not self.settings.use_merged_stages:
                        fact_prompt_map = build_agent_stage_prompts(
                            ChapterAgentContext(
                                chapter_index=segment.chapter_index,
                                normalized_title=segment.normalized_title,
                                chapter_content=stage_chapter_content,
                                previous_summary=previous_summary,
                                intake_json=intake.model_dump_json(indent=2),
                                prior_context_json=adaptive_prior_json,
                                graph_context_json=adaptive_graph_json,
                                state_summary_json=compact_state_summary_json,
                                cleaned_text=intake.cleaned_text,
                                window_summary=window_summary,
                            )
                        )
                        facts = cast(
                            ChapterFactExtractionOutput,
                            self._invoke_stage(
                                active_model,
                                fact_prompt_map['fact_extractor'],
                                ChapterFactExtractionOutput,
                            ),
                        ).ensure_minimum_facts(intake.cleaned_text)
                    self.run_service.record_job_event(
                        branch_id=branch_id,
                        chapter_index=segment.chapter_index,
                        job_id=job.id,
                        event_type='stage_completed',
                        stage='fact_extractor',
                        message=f'chapter {segment.chapter_index} fact_extractor completed',
                    )
                    self.run_service.update_job_progress(
                        branch_id,
                        segment.chapter_index,
                        current_stage='evidence_binder',
                        progress_percent=30,
                        emit_event=True,
                    )
                    if self.settings.use_merged_stages:
                        try:
                            ea_prompt_map = build_agent_stage_prompts(
                                ChapterAgentContext(
                                    chapter_index=segment.chapter_index,
                                    normalized_title=segment.normalized_title,
                                    chapter_content=stage_chapter_content,
                                    previous_summary=previous_summary,
                                    intake_json=intake.model_dump_json(indent=2),
                                    prior_context_json=adaptive_prior_json,
                                    graph_context_json=adaptive_graph_json,
                                    state_summary_json=compact_state_summary_json,
                                    cleaned_text=intake.cleaned_text,
                                    window_summary=window_summary,
                                    fact_json=facts.model_dump_json(indent=2),
                                )
                            )
                            evidence, analysis = self._invoke_merged_stage(
                                active_model,
                                ea_prompt_map['evidence_and_analysis'],
                                'evidence', EvidenceBindingOutput,
                                'analysis', ChapterAnalysisLayerOutput,
                            )
                            evidence = cast(EvidenceBindingOutput, evidence).ensure_from_facts(facts)
                            analysis = cast(
                                ChapterAnalysisLayerOutput, analysis
                            ).ensure_minimum_analysis(segment.normalized_title, evidence)
                        except (ValueError, KeyError) as merge_exc:
                            logger.warning(
                                "merged evidence+analysis failed ch%d, falling back: %s",
                                segment.chapter_index, merge_exc,
                            )
                            evidence_prompt_map = build_agent_stage_prompts(
                                ChapterAgentContext(
                                    chapter_index=segment.chapter_index,
                                    normalized_title=segment.normalized_title,
                                    chapter_content=stage_chapter_content,
                                    previous_summary=previous_summary,
                                    intake_json=intake.model_dump_json(indent=2),
                                    prior_context_json=adaptive_prior_json,
                                    graph_context_json=adaptive_graph_json,
                                    state_summary_json='{}',
                                    cleaned_text=intake.cleaned_text,
                                    window_summary='',
                                    fact_json=facts.model_dump_json(indent=2),
                                )
                            )
                            evidence = cast(
                                EvidenceBindingOutput,
                                self._invoke_stage(
                                    active_model,
                                    evidence_prompt_map['evidence_binder'],
                                    EvidenceBindingOutput,
                                ),
                            ).ensure_from_facts(facts)
                            analysis_prompt_map = build_agent_stage_prompts(
                                ChapterAgentContext(
                                    chapter_index=segment.chapter_index,
                                    normalized_title=segment.normalized_title,
                                    chapter_content=stage_chapter_content,
                                    previous_summary=previous_summary,
                                    intake_json=intake.model_dump_json(indent=2),
                                    prior_context_json=adaptive_prior_json,
                                    graph_context_json=adaptive_graph_json,
                                    state_summary_json=compact_state_summary_json,
                                    cleaned_text=intake.cleaned_text,
                                    window_summary=window_summary,
                                    fact_json=facts.model_dump_json(indent=2),
                                    evidence_bound_json=evidence.model_dump_json(indent=2),
                                )
                            )
                            analysis = cast(
                                ChapterAnalysisLayerOutput,
                                self._invoke_stage(
                                    active_model,
                                    analysis_prompt_map['analysis_generator'],
                                    ChapterAnalysisLayerOutput,
                                ),
                            ).ensure_minimum_analysis(segment.normalized_title, evidence)
                    else:
                        evidence_prompt_map = build_agent_stage_prompts(
                            ChapterAgentContext(
                                chapter_index=segment.chapter_index,
                                normalized_title=segment.normalized_title,
                                chapter_content=stage_chapter_content,
                                previous_summary=previous_summary,
                                intake_json=intake.model_dump_json(indent=2),
                                prior_context_json=adaptive_prior_json,
                                graph_context_json=adaptive_graph_json,
                                state_summary_json='{}',
                                cleaned_text=intake.cleaned_text,
                                window_summary='',
                                fact_json=facts.model_dump_json(indent=2),
                            )
                        )
                        evidence = cast(
                            EvidenceBindingOutput,
                            self._invoke_stage(
                                active_model,
                                evidence_prompt_map['evidence_binder'],
                                EvidenceBindingOutput,
                            ),
                        ).ensure_from_facts(facts)
                        self.run_service.record_job_event(
                            branch_id=branch_id,
                            chapter_index=segment.chapter_index,
                            job_id=job.id,
                            event_type='stage_completed',
                            stage='evidence_binder',
                            message=f'chapter {segment.chapter_index} evidence_binder completed',
                        )
                        self.run_service.update_job_progress(
                            branch_id,
                            segment.chapter_index,
                            current_stage='analysis_generator',
                            progress_percent=50,
                            emit_event=True,
                        )
                        compact_state_summary_json = self._compact_state_summary_json(state_summary)
                        analysis_prompt_map = build_agent_stage_prompts(
                            ChapterAgentContext(
                                chapter_index=segment.chapter_index,
                                normalized_title=segment.normalized_title,
                                chapter_content=stage_chapter_content,
                                previous_summary=previous_summary,
                                intake_json=intake.model_dump_json(indent=2),
                                prior_context_json=adaptive_prior_json,
                                graph_context_json=adaptive_graph_json,
                                state_summary_json=compact_state_summary_json,
                                cleaned_text=intake.cleaned_text,
                                window_summary=window_summary,
                                fact_json=facts.model_dump_json(indent=2),
                                evidence_bound_json=evidence.model_dump_json(indent=2),
                            )
                        )
                        analysis = cast(
                            ChapterAnalysisLayerOutput,
                            self._invoke_stage(
                                active_model,
                                analysis_prompt_map['analysis_generator'],
                                ChapterAnalysisLayerOutput,
                            ),
                        ).ensure_minimum_analysis(segment.normalized_title, evidence)
                    self.run_service.record_job_event(
                        branch_id=branch_id,
                        chapter_index=segment.chapter_index,
                        job_id=job.id,
                        event_type='stage_completed',
                        stage='analysis_generator',
                        message=f'chapter {segment.chapter_index} analysis_generator completed',
                    )
                    (
                        state_transition_notes,
                        evidence_backed_resolutions,
                        unresolved_threads,
                    ) = self._derive_state_progression(
                        state_summary,
                        facts,
                        analysis,
                    )
                    self.run_service.update_job_progress(
                        branch_id,
                        segment.chapter_index,
                        current_stage='writer_learning_lens',
                        progress_percent=65,
                        emit_event=True,
                    )
                    writer = WriterLearningLensOutput()
                    self.run_service.record_job_event(
                        branch_id=branch_id,
                        chapter_index=segment.chapter_index,
                        job_id=job.id,
                        event_type='stage_deferred',
                        stage='writer_learning_lens',
                        message=(
                            f'chapter {segment.chapter_index} writer_learning_lens deferred '
                            'for quick profile throughput'
                        ),
                    )
                    self.run_service.update_job_progress(
                        branch_id,
                        segment.chapter_index,
                        current_stage='anti_fabrication_guard',
                        progress_percent=75,
                        emit_event=True,
                    )
                    guard_context = ChapterAgentContext(
                        chapter_index=segment.chapter_index,
                        normalized_title=segment.normalized_title,
                        chapter_content=stage_chapter_content,
                        previous_summary=previous_summary,
                        intake_json=intake.model_dump_json(indent=2),
                        prior_context_json=adaptive_prior_json,
                        graph_context_json=adaptive_graph_json,
                        state_summary_json=compact_state_summary_json,
                        window_summary=window_summary,
                        cleaned_text=intake.cleaned_text,
                        fact_json=facts.model_dump_json(indent=2),
                        evidence_bound_json=evidence.model_dump_json(indent=2),
                        analysis_json=analysis.model_dump_json(indent=2),
                        writer_json=writer.model_dump_json(indent=2),
                        chapter_json=self._merge_stage_outputs(
                            segment.chapter_index,
                            segment.normalized_title,
                            facts,
                            analysis,
                            writer,
                            AntiFabricationGuardOutput(),
                            state_transition_notes,
                            evidence_backed_resolutions,
                            unresolved_threads,
                        ).model_dump_json(indent=2),
                    )
                    guard_prompt_map = build_agent_stage_prompts(guard_context)
                    guard = cast(
                        AntiFabricationGuardOutput,
                        self._invoke_stage(
                            active_model,
                            guard_prompt_map['anti_fabrication_guard'],
                            AntiFabricationGuardOutput,
                        ),
                    )
                    guard = self._state_summary_guard(
                        state_summary,
                        facts,
                        analysis,
                        guard,
                    )
                    self.run_service.record_job_event(
                        branch_id=branch_id,
                        chapter_index=segment.chapter_index,
                        job_id=job.id,
                        event_type='stage_completed',
                        stage='anti_fabrication_guard',
                        message=f'chapter {segment.chapter_index} anti_fabrication_guard completed',
                    )
                    result = self._merge_stage_outputs(
                        segment.chapter_index,
                        segment.normalized_title,
                        facts,
                        analysis,
                        writer,
                        guard,
                        state_transition_notes,
                        evidence_backed_resolutions,
                        unresolved_threads,
                    )
                    stage_payload = {
                        'intake': intake.model_dump(mode='json'),
                        'facts': facts.model_dump(mode='json'),
                        'evidence': evidence.model_dump(mode='json'),
                        'analysis': analysis.model_dump(mode='json'),
                        'writer': writer.model_dump(mode='json'),
                        'guard': guard.model_dump(mode='json'),
                    }
                    prompt_metrics = self._prompt_metrics(
                        chapter_intake=prompts['chapter_intake'],
                        fact_extractor=fact_prompt_map['fact_extractor'],
                        evidence_binder=evidence_prompt_map['evidence_binder'],
                        analysis_generator=analysis_prompt_map['analysis_generator'],
                        anti_fabrication_guard=guard_prompt_map['anti_fabrication_guard'],
                    )
                    if self._is_sparse_result(result):
                        raise ValueError('stage pipeline produced sparse result')
                except Exception as stage_exc:
                    self.run_service.record_job_event(
                        branch_id=branch_id,
                        chapter_index=segment.chapter_index,
                        job_id=job.id,
                        event_type='stage_failed',
                        stage='small_model_pipeline',
                        level='warning',
                        message=str(stage_exc),
                    )
                    self.run_service.update_job_progress(
                        branch_id,
                        segment.chapter_index,
                        current_stage='monolithic_fallback',
                        progress_percent=55,
                        emit_event=True,
                    )
                    try:
                        result = self._invoke_monolithic_analysis(
                            fallback_model,
                            segment.chapter_index,
                            segment.normalized_title,
                            chapter_content,
                        )
                        stage_payload = {'stage_error': str(stage_exc), 'fallback': 'monolithic'}
                        prompt_metrics = {'prompt_char_counts': {}, 'total_prompt_chars': 0}
                    except Exception as fallback_exc:
                        if not self._is_provider_unavailable_error(fallback_exc):
                            raise
                        logger.warning(
                            "LLM unavailable for branch=%s chapter=%d; falling back to "
                            "local-heuristic key_entities (will be tagged extraction_source=heuristic "
                            "and skipped by downstream guards). stage_error=%s fallback_error=%s",
                            branch_id,
                            segment.chapter_index,
                            str(stage_exc)[:200],
                            str(fallback_exc)[:200],
                        )
                        result = self._build_local_heuristic_analysis(
                            segment.chapter_index,
                            segment.normalized_title,
                            chapter_content,
                        )
                        stage_payload = {
                            'stage_error': str(stage_exc),
                            'fallback_error': str(fallback_exc),
                            'fallback': 'local-heuristic',
                        }
                        prompt_metrics = {'prompt_char_counts': {}, 'total_prompt_chars': 0}

                response_text = json.dumps(stage_payload, ensure_ascii=False, indent=2)
                raw_result = result.model_dump(mode='json')
                self.run_service.record_raw_output(
                    run_id,
                    branch_id,
                    segment.chapter_index,
                    job.attempts,
                    response_text,
                    parsed_json=result.model_dump(mode='json'),
                    parse_status='parsed',
                    parse_error=None,
                    invocation_metadata={
                        'model_name': (
                            self.settings.llm_fallback_model_name
                            if stage_payload.get('fallback')
                            else self.settings.llm_stage_model_name
                        ),
                        'base_url': self.settings.llm_base_url,
                        'pipeline': 'small-model-skills-v1',
                        **prompt_metrics,
                    },
                )
                self.run_service.update_job_progress(
                    branch_id,
                    segment.chapter_index,
                    current_stage='quality_gate',
                    progress_percent=85,
                    emit_event=True,
                )
                try:
                    self_eval = self.self_evaluation.evaluate(
                        result,
                        facts if 'facts' in dir() else ChapterFactExtractionOutput(),
                        evidence if 'evidence' in dir() else EvidenceBindingOutput(),
                        prior_context,
                    )
                    if self_eval.issues:
                        existing_notes = list(result.quality_gate_notes or [])
                        for issue in self_eval.issues[:5]:
                            existing_notes.append(
                                f'[self-eval/{issue.severity}] {issue.description}'
                            )
                        result = result.model_copy(update={
                            'quality_gate_notes': existing_notes,
                            'needs_human_review': (
                                result.needs_human_review or not self_eval.passed
                            ),
                        })
                except Exception as exc:  # noqa: BLE001
                    logger.debug("self-evaluation failed ch%d: %s", segment.chapter_index, exc)
                try:
                    result = ClaimGroundingService.apply_grounding_to_result(
                        chapter_content, result,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("claim grounding failed ch%d: %s", segment.chapter_index, exc)
                try:
                    local_facts = facts if 'facts' in dir() else ChapterFactExtractionOutput()
                    local_evidence = evidence if 'evidence' in dir() else EvidenceBindingOutput()
                    result, local_facts, repair_report = AutoRepairService.repair(
                        result, local_facts, local_evidence, chapter_content,
                    )
                    if repair_report.actions_taken:
                        logger.info(
                            "auto-repair ch%d: %d fixes", segment.chapter_index,
                            len(repair_report.actions_taken),
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("auto-repair failed ch%d: %s", segment.chapter_index, exc)
                gate = QualityGateService.evaluate(chapter_content, result)
                result = result.model_copy(update={
                    'quality_gate_notes': gate.notes,
                    'hook_score': gate.hook_score,
                    'needs_human_review': result.needs_human_review or gate.needs_human_review,
                })
                self.run_service.update_job_progress(
                    branch_id,
                    segment.chapter_index,
                    current_stage='artifact_persist',
                    progress_percent=90,
                    emit_event=True,
                )
                writer_deferred = not bool(result.writer_learning_notes)
                deconstruction_profile = self._build_deconstruction_profile(
                    chapter_content=chapter_content,
                    stage_payload=stage_payload,
                    writer_deferred=writer_deferred,
                )
                artifact = self.run_service.record_chapter_artifact(
                    branch_id,
                    segment.chapter_index,
                    self._with_deconstruction_profile(
                        result.model_dump(mode='json'),
                        deconstruction_profile,
                    ),
                    source_kind='model',
                    participates_in_downstream=True,
                )
                self.run_service.update_job_progress(
                    branch_id,
                    segment.chapter_index,
                    current_stage='materialization',
                    progress_percent=95,
                    emit_event=True,
                )
                mat_start = time.time()
                self.retrieval_service.materialize_for_artifact(artifact.id)
                self.fact_service.materialize_for_artifact(artifact.id)
                self.graph_service.materialize_for_artifact(artifact.id)
                mat_elapsed = time.time() - mat_start
                if mat_elapsed > 60.0:
                    logger.warning(
                        "materialization slow ch%d: %.1fs",
                        segment.chapter_index, mat_elapsed,
                    )
                self._update_foreshadowing_lifecycle(
                    branch_id, segment.chapter_index, stage_payload, state_summary,
                )
                try:
                    self.entity_resolution.build_alias_map(branch_id)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("entity resolution failed ch%d: %s", segment.chapter_index, exc)
                self._update_causal_graph(
                    branch_id, segment.chapter_index, stage_payload, state_summary,
                )
                try:
                    self.confidence_calibration.calibrate_chapter_facts(
                        branch_id, segment.chapter_index,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("confidence calibration failed ch%d: %s", segment.chapter_index, exc)
                try:
                    self.domain_dictionary.update_from_chapter(branch_id, segment.chapter_index)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("domain dictionary update failed ch%d: %s", segment.chapter_index, exc)
                self.fact_service.materialize_window_if_ready(
                    branch_id,
                    segment.chapter_index,
                    self.settings.cross_chapter_window,
                )
                # Loom: memory consolidation (shadow / enabled mode)
                if self.settings.loom_memory_mode in ("shadow", "enabled", "ab"):
                    try:
                        loom_result = self.memory_consolidation.consolidate(
                            branch_id, segment.chapter_index
                        )
                        self.run_service.record_job_event(
                            branch_id=branch_id,
                            chapter_index=segment.chapter_index,
                            event_type="loom_consolidation_complete",
                            stage="loom_memory",
                            message=(
                                f"loom consolidation: {loom_result.total_conflicts} conflicts "
                                f"(contradictions={len(loom_result.contradictions)}, "
                                f"evolutions={len(loom_result.evolutions)}, "
                                f"ambiguities={len(loom_result.ambiguities)})"
                            ),
                            payload_json=loom_result.to_operator_signal(),
                        )
                    except Exception as _loom_exc:  # noqa: BLE001
                        # Loom is non-blocking – log and continue
                        self.run_service.record_job_event(
                            branch_id=branch_id,
                            chapter_index=segment.chapter_index,
                            event_type="loom_consolidation_failed",
                            stage="loom_memory",
                            level="warning",
                            message=str(_loom_exc),
                            payload_json={"non_blocking": True},
                        )
                self.run_service.complete_chapter_job(branch_id, segment.chapter_index)
                self.run_service.record_job_event(
                    branch_id=branch_id,
                    chapter_index=segment.chapter_index,
                    event_type="stage_deferred",
                    stage="risk_aggregation",
                    level="info",
                    message=(
                        f"chapter {segment.chapter_index} risk_aggregation deferred "
                        "from quick sync path"
                    ),
                    payload_json={"non_blocking": True, "deferred": True},
                )
                artifact_ids.append(artifact.id)
                previous_summary = result.chapter_summary
            except Exception as exc:
                if 'artifact' in locals() and artifact is not None:
                    self.run_service.restore_previous_active_artifact(
                        branch_id,
                        segment.chapter_index,
                        artifact.id,
                    )
                self.run_service.record_raw_output(
                    run_id,
                    branch_id,
                    segment.chapter_index,
                    job.attempts,
                    response_text,
                    parsed_json=raw_result,
                    parse_status='failed',
                    parse_error=str(exc),
                    invocation_metadata={
                        'model_name': (
                            self.settings.llm_fallback_model_name
                            if stage_payload.get('fallback')
                            else self.settings.llm_stage_model_name
                        ),
                        'base_url': self.settings.llm_base_url,
                        'pipeline': 'small-model-skills-v1',
                        **prompt_metrics,
                    },
                )
                self.run_service.fail_chapter_job(branch_id, segment.chapter_index, str(exc))
                raise

        return artifact_ids
