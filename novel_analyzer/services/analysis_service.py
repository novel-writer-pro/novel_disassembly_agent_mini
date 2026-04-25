"""Live chapter analysis service backed by the configured LLM."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import cast

from langchain_core.messages import BaseMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.agent.pipeline import ChapterAgentContext, build_agent_stage_prompts
from novel_analyzer.config.settings import Settings, get_settings
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
from novel_analyzer.services.context_service import ContextService
from novel_analyzer.services.fact_service import FactService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.quality_gate_service import QualityGateService
from novel_analyzer.services.retrieval_service import RetrievalService
from novel_analyzer.services.run_service import RunService


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

    @staticmethod
    def _serialize_message_content(message: BaseMessage) -> str:
        """Normalize model content to plain text for persistence."""

        content = message.content
        if isinstance(content, list):
            return "\n".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        return str(content)

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
        return cast(dict[str, object], json.loads(stripped[start : end + 1]))

    def _invoke_with_retry(self, model: object, prompt: str) -> BaseMessage:
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                return cast(BaseMessage, model.invoke(prompt))  # type: ignore[attr-defined]
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == 3:
                    raise
                time.sleep(float(attempt))
        assert last_error is not None
        raise last_error

    def _invoke_stage(self, model: object, prompt: str, schema: type[object]) -> object:
        response = self._invoke_with_retry(model, prompt)
        raw = self._extract_json_payload(response)
        return schema.model_validate(raw)  # type: ignore[attr-defined]


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
    def _is_sparse_result(result: ChapterAnalysisOutput) -> bool:
        return (
            not result.chapter_summary.strip()
            and not result.key_entities
            and not result.key_events
            and not result.continuity_notes
        )

    @staticmethod
    def _merge_stage_outputs(
        chapter_index: int,
        normalized_title: str,
        facts: ChapterFactExtractionOutput,
        analysis: ChapterAnalysisLayerOutput,
        writer: WriterLearningLensOutput,
        guard: AntiFabricationGuardOutput,
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
            chapter_summary=(
                analysis.summary.short
                or analysis.summary.one_sentence
                or analysis.summary.detailed
            ),
            key_entities=[item.label for item in facts.characters],
            key_events=[item.label for item in facts.events],
            continuity_notes=analysis.continuity_notes,
            writer_learning_notes=writer_notes,
            unsupported_inferences=guard.unsupported_inferences + guard.overclaim_flags,
            ambiguous_points=guard.ambiguous_points,
            needs_human_review=guard.needs_human_review,
        )

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
            try:
                chapter_content = full_text[segment.start_offset : segment.end_offset].strip()
                previous_summary = self.context_service.previous_summary(
                    branch_id,
                    segment.chapter_index,
                )
                prior_context = self.context_service.fact_context_json(
                    branch_id,
                    segment.chapter_index,
                )
                graph_context = self.context_service.graph_context_json(
                    branch_id,
                    segment.chapter_index,
                )
                window_summary = self.context_service.window_summary(
                    branch_id,
                    segment.chapter_index,
                )
                prior_context_json = json.dumps(prior_context, ensure_ascii=False, indent=2)
                graph_context_json = json.dumps(graph_context, ensure_ascii=False, indent=2)
                stage_payload: dict[str, object] = {}
                try:
                    prompts = build_agent_stage_prompts(
                        ChapterAgentContext(
                            chapter_index=segment.chapter_index,
                            normalized_title=segment.normalized_title,
                            chapter_content=chapter_content,
                            previous_summary=previous_summary,
                            prior_context_json=prior_context_json,
                            graph_context_json=graph_context_json,
                            window_summary=window_summary,
                        )
                    )
                    intake = cast(
                        ChapterIntakeOutput,
                        self._invoke_stage(
                            stage_model,
                            prompts['chapter_intake'],
                            ChapterIntakeOutput,
                        ),
                    )
                    fact_prompt_map = build_agent_stage_prompts(
                        ChapterAgentContext(
                            chapter_index=segment.chapter_index,
                            normalized_title=segment.normalized_title,
                            chapter_content=chapter_content,
                            previous_summary=previous_summary,
                            intake_json=intake.model_dump_json(indent=2),
                            prior_context_json=prior_context_json,
                            graph_context_json=graph_context_json,
                            cleaned_text=intake.cleaned_text,
                            window_summary=window_summary,
                        )
                    )
                    facts = cast(
                        ChapterFactExtractionOutput,
                        self._invoke_stage(
                                    stage_model,
                            fact_prompt_map['fact_extractor'],
                            ChapterFactExtractionOutput,
                        ),
                    ).ensure_minimum_facts(intake.cleaned_text)
                    evidence_prompt_map = build_agent_stage_prompts(
                        ChapterAgentContext(
                            chapter_index=segment.chapter_index,
                            normalized_title=segment.normalized_title,
                            chapter_content=chapter_content,
                            previous_summary=previous_summary,
                            intake_json=intake.model_dump_json(indent=2),
                            prior_context_json=prior_context_json,
                            graph_context_json=graph_context_json,
                            cleaned_text=intake.cleaned_text,
                            window_summary=window_summary,
                            fact_json=facts.model_dump_json(indent=2),
                        )
                    )
                    evidence = cast(
                        EvidenceBindingOutput,
                        self._invoke_stage(
                            stage_model,
                            evidence_prompt_map['evidence_binder'],
                            EvidenceBindingOutput,
                        ),
                    ).ensure_from_facts(facts)
                    analysis_prompt_map = build_agent_stage_prompts(
                        ChapterAgentContext(
                            chapter_index=segment.chapter_index,
                            normalized_title=segment.normalized_title,
                            chapter_content=chapter_content,
                            previous_summary=previous_summary,
                            intake_json=intake.model_dump_json(indent=2),
                            prior_context_json=prior_context_json,
                            graph_context_json=graph_context_json,
                            cleaned_text=intake.cleaned_text,
                            window_summary=window_summary,
                            fact_json=facts.model_dump_json(indent=2),
                            evidence_bound_json=evidence.model_dump_json(indent=2),
                        )
                    )
                    analysis = cast(
                        ChapterAnalysisLayerOutput,
                        self._invoke_stage(
                            stage_model,
                            analysis_prompt_map['analysis_generator'],
                            ChapterAnalysisLayerOutput,
                        ),
                    ).ensure_minimum_analysis(segment.normalized_title, evidence)
                    writer = cast(
                        WriterLearningLensOutput,
                        self._invoke_stage(
                            stage_model,
                            analysis_prompt_map['writer_learning_lens'],
                            WriterLearningLensOutput,
                        ),
                    ).ensure_minimum_writer_notes(
                        segment.normalized_title,
                        analysis.summary.short or analysis.summary.one_sentence,
                    )
                    guard_context = ChapterAgentContext(
                        chapter_index=segment.chapter_index,
                        normalized_title=segment.normalized_title,
                        chapter_content=chapter_content,
                        previous_summary=previous_summary,
                        intake_json=intake.model_dump_json(indent=2),
                        prior_context_json=prior_context_json,
                        graph_context_json=graph_context_json,
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
                        ).model_dump_json(indent=2),
                    )
                    guard_prompt_map = build_agent_stage_prompts(guard_context)
                    guard = cast(
                        AntiFabricationGuardOutput,
                        self._invoke_stage(
                            stage_model,
                            guard_prompt_map['anti_fabrication_guard'],
                            AntiFabricationGuardOutput,
                        ),
                    )
                    result = self._merge_stage_outputs(
                        segment.chapter_index,
                        segment.normalized_title,
                        facts,
                        analysis,
                        writer,
                        guard,
                    )
                    stage_payload = {
                        'intake': intake.model_dump(mode='json'),
                        'facts': facts.model_dump(mode='json'),
                        'evidence': evidence.model_dump(mode='json'),
                        'analysis': analysis.model_dump(mode='json'),
                        'writer': writer.model_dump(mode='json'),
                        'guard': guard.model_dump(mode='json'),
                    }
                    if self._is_sparse_result(result):
                        raise ValueError('stage pipeline produced sparse result')
                except Exception as stage_exc:
                    result = self._invoke_monolithic_analysis(
                        fallback_model,
                        segment.chapter_index,
                        segment.normalized_title,
                        chapter_content,
                    )
                    stage_payload = {'stage_error': str(stage_exc), 'fallback': 'monolithic'}

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
                    },
                )
                gate = QualityGateService.evaluate(chapter_content, result)
                result = result.model_copy(update={
                    'quality_gate_notes': gate.notes,
                    'hook_score': gate.hook_score,
                    'needs_human_review': result.needs_human_review or gate.needs_human_review,
                })
                artifact = self.run_service.record_chapter_artifact(
                    branch_id,
                    segment.chapter_index,
                    result.model_dump(mode='json'),
                    source_kind='model',
                    participates_in_downstream=True,
                )
                self.retrieval_service.materialize_for_artifact(artifact.id)
                self.fact_service.materialize_for_artifact(artifact.id)
                self.graph_service.materialize_for_artifact(artifact.id)
                self.fact_service.materialize_window_if_ready(
                    branch_id,
                    segment.chapter_index,
                    self.settings.cross_chapter_window,
                )
                self.run_service.complete_chapter_job(branch_id, segment.chapter_index)
                artifact_ids.append(artifact.id)
                previous_summary = result.chapter_summary
            except Exception as exc:
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
                    },
                )
                self.run_service.fail_chapter_job(branch_id, segment.chapter_index, str(exc))
                raise

        return artifact_ids
