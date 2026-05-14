from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import (
    ChapterArtifact,
    FactRecord,
    GraphEdge,
    GraphNode,
    RiskSemanticSignalRecord,
)
from novel_analyzer.database.session import create_session_factory


@dataclass
class DimensionScore:
    name: str
    score: float
    max_score: float = 1.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkReport:
    model_name: str
    branch_id: str
    chapters_tested: list[int]
    elapsed_seconds: float
    deconstruction_score: float
    imitation_score: float
    risk_check_score: float
    composite_score: float
    dimensions: list[DimensionScore] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "branch_id": self.branch_id,
            "chapters_tested": self.chapters_tested,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "scores": {
                "deconstruction": round(self.deconstruction_score, 4),
                "imitation": round(self.imitation_score, 4),
                "risk_check": round(self.risk_check_score, 4),
                "composite": round(self.composite_score, 4),
            },
            "dimensions": [
                {"name": d.name, "score": round(d.score, 4), "details": d.details}
                for d in self.dimensions
            ],
        }


class ModelBenchmarkService:

    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def run_benchmark(
        self,
        branch_id: str,
        chapters: list[int],
        llm_client: Any | None = None,
    ) -> BenchmarkReport:
        t0 = time.time()

        decon_dims = self._evaluate_deconstruction(branch_id, chapters)
        imit_dims = self._evaluate_imitation(branch_id, chapters, llm_client)
        risk_dims = self._evaluate_risk_check(branch_id, chapters)

        decon_score = self._avg_score(decon_dims)
        imit_score = self._avg_score(imit_dims)
        risk_score = self._avg_score(risk_dims)
        composite = decon_score * 0.3 + imit_score * 0.4 + risk_score * 0.3

        return BenchmarkReport(
            model_name=self.settings.llm_model_name,
            branch_id=branch_id,
            chapters_tested=chapters,
            elapsed_seconds=time.time() - t0,
            deconstruction_score=decon_score,
            imitation_score=imit_score,
            risk_check_score=risk_score,
            composite_score=composite,
            dimensions=decon_dims + imit_dims + risk_dims,
        )

    def _evaluate_deconstruction(self, branch_id: str, chapters: list[int]) -> list[DimensionScore]:
        entity_scores: list[float] = []
        event_scores: list[float] = []
        graph_scores: list[float] = []

        for ch in chapters:
            entities = self.session.scalar(
                select(func.count(FactRecord.id))
                .where(FactRecord.branch_id == branch_id)
                .where(FactRecord.chapter_index == ch)
                .where(FactRecord.fact_type == "entity")
                .where(FactRecord.deleted_at.is_(None))
            ) or 0

            events = self.session.scalar(
                select(func.count(FactRecord.id))
                .where(FactRecord.branch_id == branch_id)
                .where(FactRecord.chapter_index == ch)
                .where(FactRecord.fact_type == "event")
                .where(FactRecord.deleted_at.is_(None))
            ) or 0

            edges = self.session.scalar(
                select(func.count(GraphEdge.id))
                .where(GraphEdge.branch_id == branch_id)
                .where(GraphEdge.chapter_first_seen == ch)
                .where(GraphEdge.deleted_at.is_(None))
            ) or 0

            entity_scores.append(min(1.0, entities / 5.0))
            event_scores.append(min(1.0, events / 8.0))
            graph_scores.append(min(1.0, edges / 30.0))

        return [
            DimensionScore(
                name="entity_extraction",
                score=sum(entity_scores) / len(entity_scores) if entity_scores else 0,
                details={"per_chapter": entity_scores},
            ),
            DimensionScore(
                name="event_extraction",
                score=sum(event_scores) / len(event_scores) if event_scores else 0,
                details={"per_chapter": event_scores},
            ),
            DimensionScore(
                name="graph_construction",
                score=sum(graph_scores) / len(graph_scores) if graph_scores else 0,
                details={"per_chapter": graph_scores},
            ),
        ]

    def _evaluate_imitation(
        self, branch_id: str, chapters: list[int], llm_client: Any | None
    ) -> list[DimensionScore]:
        from novel_analyzer.services.chapter_imitation_service import ChapterImitationService
        from novel_analyzer.services.reference_eval_service import ReferenceEvalService

        cis = ChapterImitationService(self.session, self.settings)
        ref_svc = ReferenceEvalService(llm_client=llm_client)

        fidelity_scores: list[float] = []
        structure_scores: list[float] = []
        character_scores: list[float] = []
        style_scores: list[float] = []

        for ch in chapters:
            try:
                title, original_text = cis._source_chapter_text(branch_id, ch)
                draft = cis.build_skeleton_draft(
                    branch_id,
                    source_chapter_index=ch,
                    target_goal=f"延续第{ch}章情节",
                )
                draft_text = draft.draft_text

                if llm_client is not None:
                    try:
                        draft = cis.build_llm_draft(
                            branch_id,
                            source_chapter_index=ch,
                            target_goal=f"延续第{ch}章情节",
                        )
                        draft_text = draft.draft_text
                    except Exception:
                        pass

                result = ref_svc.evaluate(
                    branch_id=branch_id,
                    chapter_index=ch,
                    original_text=original_text,
                    draft_text=draft_text,
                    chapter_goal=f"延续第{ch}章情节",
                )
                fidelity_scores.append(result.overall_fidelity)
                for dim_name, scores_list in [
                    ("structure_fidelity", structure_scores),
                    ("character_fidelity", character_scores),
                    ("style_fidelity", style_scores),
                ]:
                    dim = result.dimensions.get(dim_name)
                    if dim and hasattr(dim, "score"):
                        scores_list.append(dim.score)
                    else:
                        scores_list.append(0.5)
            except Exception:
                fidelity_scores.append(0.0)
                structure_scores.append(0.0)
                character_scores.append(0.0)
                style_scores.append(0.0)

        return [
            DimensionScore(
                name="overall_fidelity",
                score=sum(fidelity_scores) / len(fidelity_scores) if fidelity_scores else 0,
                details={"per_chapter": fidelity_scores},
            ),
            DimensionScore(
                name="structure_fidelity",
                score=sum(structure_scores) / len(structure_scores) if structure_scores else 0,
            ),
            DimensionScore(
                name="character_fidelity",
                score=sum(character_scores) / len(character_scores) if character_scores else 0,
            ),
            DimensionScore(
                name="style_fidelity",
                score=sum(style_scores) / len(style_scores) if style_scores else 0,
            ),
        ]

    def _evaluate_risk_check(self, branch_id: str, chapters: list[int]) -> list[DimensionScore]:
        signal_coverage_scores: list[float] = []
        signal_quality_scores: list[float] = []

        for ch in chapters:
            signal_count = self.session.scalar(
                select(func.count(RiskSemanticSignalRecord.id))
                .where(RiskSemanticSignalRecord.branch_id == branch_id)
                .where(RiskSemanticSignalRecord.chapter_index == ch)
                .where(RiskSemanticSignalRecord.deleted_at.is_(None))
            ) or 0

            high_conf_count = self.session.scalar(
                select(func.count(RiskSemanticSignalRecord.id))
                .where(RiskSemanticSignalRecord.branch_id == branch_id)
                .where(RiskSemanticSignalRecord.chapter_index == ch)
                .where(RiskSemanticSignalRecord.confidence >= 0.7)
                .where(RiskSemanticSignalRecord.deleted_at.is_(None))
            ) or 0

            signal_coverage_scores.append(min(1.0, signal_count / 10.0))
            signal_quality_scores.append(
                high_conf_count / signal_count if signal_count > 0 else 0.0
            )

        conflict_nodes = self.session.scalar(
            select(func.count(GraphNode.id))
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.node_type == "conflict")
            .where(GraphNode.deleted_at.is_(None))
        ) or 0
        foreshadow_nodes = self.session.scalar(
            select(func.count(GraphNode.id))
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.node_type == "foreshadow")
            .where(GraphNode.deleted_at.is_(None))
        ) or 0
        total_nodes = self.session.scalar(
            select(func.count(GraphNode.id))
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.deleted_at.is_(None))
        ) or 1

        narrative_awareness = (conflict_nodes + foreshadow_nodes) / total_nodes

        return [
            DimensionScore(
                name="risk_signal_coverage",
                score=sum(signal_coverage_scores) / len(signal_coverage_scores) if signal_coverage_scores else 0,
                details={"per_chapter": signal_coverage_scores},
            ),
            DimensionScore(
                name="risk_signal_quality",
                score=sum(signal_quality_scores) / len(signal_quality_scores) if signal_quality_scores else 0,
            ),
            DimensionScore(
                name="narrative_risk_awareness",
                score=min(1.0, narrative_awareness * 5),
                details={"conflict_nodes": conflict_nodes, "foreshadow_nodes": foreshadow_nodes},
            ),
        ]

    @staticmethod
    def _avg_score(dims: list[DimensionScore]) -> float:
        if not dims:
            return 0.0
        return sum(d.score for d in dims) / len(dims)
