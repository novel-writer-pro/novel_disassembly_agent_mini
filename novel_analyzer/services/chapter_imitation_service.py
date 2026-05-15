"""Chapter imitation / continuation planning skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import ChapterSegment, NovelSource, RunBranch
from novel_analyzer.domain.schemas import (
    ChapterAnalysisOutput,
    ChapterImitationDraft,
    ChapterImitationComparisonReport,
    ChapterImitationGateReport,
    ChapterImitationIterationReport,
    ChapterImitationIterationRound,
    ChapterImitationRiskReport,
    ChapterImitationReviewReport,
    ChapterImitationPlan,
    ChapterImitationScoreReport,
    ChapterPlanningIntent,
    ChapterRiskCard,
    MultiChapterImitationConsistencyReport,
    MultiChapterImitationStep,
)
from novel_analyzer.llm.client import build_chat_model
from novel_analyzer.llm.prompts import build_chapter_imitation_prompt
from novel_analyzer.services.next_chapter_planner_service import (
    NextChapterPlannerService,
    PlannerContextWindow,
)
from novel_analyzer.services.quality_gate_service import QualityGateService
from novel_analyzer.services.risk_audit_service import RiskAuditService
from novel_analyzer.services.run_service import RunService


@dataclass(frozen=True, slots=True)
class ChapterImitationMethod:
    """Documented imitation workflow configuration."""

    compare_window: int = 3
    preserve_title_style: bool = True


class ChapterImitationService:
    """Build an imitation plan and deterministic skeleton draft for one chapter."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.run_service = RunService(session)
        self.next_chapter_planner = NextChapterPlannerService(session)

    @staticmethod
    def _normalize_steering_pack(steering_pack: dict[str, object] | None) -> dict[str, list[str]]:
        pack = steering_pack or {}
        def _string_list(key: str) -> list[str]:
            value = pack.get(key, [])
            if not isinstance(value, list):
                return []
            return [str(item).strip() for item in value if str(item).strip()]
        return {
            "worldview_capsule": _string_list("worldview_capsule"),
            "trope_axes": _string_list("trope_axes"),
            "innovation_directives": _string_list("innovation_directives"),
            "taboo_innovations": _string_list("taboo_innovations"),
            "external_knowledge_refs": _string_list("external_knowledge_refs"),
        }

    def build_imitation_plan(
        self,
        branch_id: str,
        *,
        source_chapter_index: int,
        target_goal: str,
        method: ChapterImitationMethod | None = None,
        steering_pack: dict[str, object] | None = None,
    ) -> ChapterImitationPlan:
        effective = method or ChapterImitationMethod()
        steering = self._normalize_steering_pack(steering_pack)
        intent = ChapterPlanningIntent(
            primary_goal=target_goal,
            emphasis=["保持人物连续性", "保持冲突推进", "保持风格约束"],
            forbidden_moves=["不要无铺垫升级战力", "不要引入未准备的大设定"],
            preferred_tone="克制务实",
            pace="steady",
        )
        context = self.next_chapter_planner.build_context(
            branch_id,
            intent=intent,
            window=PlannerContextWindow(recent_chapter_count=effective.compare_window),
        )

        style_axes = [
            "沿用原章的叙事视角与信息释放顺序",
            "沿用原章的冲突-应对-收束节奏",
            "优先保持人物选择逻辑，而非表面句式模仿",
        ]
        scene_beats = [
            "承接上一章结果并明确当前需求/目标",
            "通过一次身份/资源/关系阻力制造推进成本",
            "让主角给出克制但更坚定的行动回应",
            "章尾给出下一步可执行钩子",
        ]
        if steering["innovation_directives"]:
            scene_beats.extend(f"创新导向：{item}" for item in steering["innovation_directives"][:2])
        if steering["trope_axes"]:
            style_axes.extend(f"题材套路轴：{item}" for item in steering["trope_axes"][:3])
        if steering["worldview_capsule"]:
            style_axes.extend(f"世界观外置胶囊：{item}" for item in steering["worldview_capsule"][:3])

        return ChapterImitationPlan(
            source_chapter_index=source_chapter_index,
            target_goal=target_goal,
            style_axes=style_axes,
            scene_beats=scene_beats,
            hard_constraints=(
                context.world_rules[:5]
                + context.forbidden_moves[:3]
                + [f"禁止创新越界：{item}" for item in steering["taboo_innovations"][:3]]
            ),
            soft_constraints=(
                context.relationship_state_notes[:3]
                + context.unresolved_threads[:3]
                + [f"外置知识参考：{item}" for item in steering["external_knowledge_refs"][:3]]
            ),
            risk_focus=context.recent_risk_signals[:3] + [f"创新关注点：{item}" for item in steering["innovation_directives"][:2]],
            worldview_capsule=steering["worldview_capsule"],
            trope_axes=steering["trope_axes"],
            innovation_directives=steering["innovation_directives"],
            taboo_innovations=steering["taboo_innovations"],
            external_knowledge_refs=steering["external_knowledge_refs"],
        )

    def build_skeleton_draft(
        self,
        branch_id: str,
        *,
        source_chapter_index: int,
        target_goal: str,
        method: ChapterImitationMethod | None = None,
        steering_pack: dict[str, object] | None = None,
    ) -> ChapterImitationDraft:
        plan = self.build_imitation_plan(
            branch_id,
            source_chapter_index=source_chapter_index,
            target_goal=target_goal,
            method=method,
            steering_pack=steering_pack,
        )
        title, source_text = self._source_chapter_text(branch_id, source_chapter_index)
        draft_title = title
        draft_text = self._render_skeleton_text(title=title, plan=plan)
        comparison_notes = [
            "原章更强调‘求助受阻后转入自我修炼’的结构。",
            "仿写草案应保持‘目标受阻 -> 克制反应 -> 行动转向’的骨架。",
            "当前 skeleton 只提供结构化草案，不主张直接替代正文。",
        ]
        risk_gate_notes = [
            "生成后必须过 character_ooc / plot_logic_consistency 门控。",
            "如涉及规则推进，还应补 world_rule_consistency 复核。",
        ]
        return ChapterImitationDraft(
            source_chapter_index=source_chapter_index,
            original_title=title,
            draft_title=draft_title,
            draft_text=draft_text,
            method_notes=plan.style_axes + plan.scene_beats,
            comparison_notes=comparison_notes + [f"原章长度={len(source_text)} 字符"],
            risk_gate_notes=risk_gate_notes + plan.risk_focus,
        )

    def build_llm_draft(
        self,
        branch_id: str,
        *,
        source_chapter_index: int,
        target_goal: str,
        method: ChapterImitationMethod | None = None,
        model_name: str | None = None,
        steering_pack: dict[str, object] | None = None,
        mapping_pack: dict[str, object] | None = None,
    ) -> ChapterImitationDraft:
        plan = self.build_imitation_plan(
            branch_id,
            source_chapter_index=source_chapter_index,
            target_goal=target_goal,
            method=method,
            steering_pack=steering_pack,
        )
        title, source_text = self._source_chapter_text(branch_id, source_chapter_index)

        previous_summary = ""
        active_characters: list[str] = []
        unresolved_threads: list[str] = []
        if self.settings.loom_memory_mode in ("enabled", "ab") and source_chapter_index >= 10:
            try:
                from novel_analyzer.services.memory_assembler_service import MemoryAssemblerService
                mem_svc = MemoryAssemblerService(self.session)
                mem = mem_svc.assemble(branch_id, target_chapter_index=source_chapter_index + 1)
                previous_summary = mem.recent_summary
            except Exception:  # noqa: BLE001
                pass

        prompt = build_chapter_imitation_prompt(
            source_chapter_index=source_chapter_index,
            source_title=title,
            source_excerpt=source_text[:2500],
            target_goal=target_goal,
            style_axes=plan.style_axes,
            scene_beats=plan.scene_beats + [f"世界观胶囊：{item}" for item in plan.worldview_capsule[:2]],
            hard_constraints=plan.hard_constraints + [f"禁止创新越界：{item}" for item in plan.taboo_innovations[:2]],
            soft_constraints=plan.soft_constraints + [f"题材套路：{item}" for item in plan.trope_axes[:2]] + [f"创新导向：{item}" for item in plan.innovation_directives[:2]],
            previous_summary=previous_summary,
            active_characters=active_characters,
            unresolved_threads=unresolved_threads,
            mapping_pack=mapping_pack,
        )
        model = build_chat_model(self.settings, model_name=model_name)
        response = model.invoke(prompt)
        payload = self._extract_json_payload(response.content if hasattr(response, "content") else response)
        return ChapterImitationDraft.model_validate(
            {
                "source_chapter_index": source_chapter_index,
                "original_title": title,
                "draft_title": payload.get("draft_title") or title,
                "draft_text": payload.get("draft_text") or "",
                "method_notes": payload.get("method_notes") or plan.style_axes + plan.scene_beats,
                "comparison_notes": payload.get("comparison_notes") or [],
                "risk_gate_notes": payload.get("risk_gate_notes") or plan.risk_focus,
            }
        )

    def _source_chapter_text(self, branch_id: str, chapter_index: int) -> tuple[str, str]:
        branch = self.session.scalar(select(RunBranch).where(RunBranch.id == branch_id))
        if branch is None:
            raise ValueError(f"Unknown branch_id: {branch_id}")
        run = branch.run
        novel = self.session.scalar(select(NovelSource).where(NovelSource.id == run.novel_id))
        if novel is None:
            raise ValueError("branch is missing novel source")
        manifest = run.manifest
        segment = self.session.scalar(
            select(ChapterSegment)
            .where(ChapterSegment.manifest_id == manifest.id)
            .where(ChapterSegment.chapter_index == chapter_index)
        )
        if segment is None:
            raise ValueError(f"Unknown chapter_index: {chapter_index}")
        full_text = Path(novel.source_path).read_text(encoding="utf-8", errors="ignore")
        return segment.normalized_title, full_text[segment.start_offset : segment.end_offset].strip()

    def compare_with_source(
        self,
        branch_id: str,
        *,
        source_chapter_index: int,
        draft: ChapterImitationDraft,
    ) -> ChapterImitationComparisonReport:
        title, source_text = self._source_chapter_text(branch_id, source_chapter_index)
        structure_overlap_notes = [
            "是否保留了‘目标受阻 -> 克制反应 -> 行动转向’骨架。",
            "是否保留了原章的章尾钩子功能，而不是只模仿表面句式。",
        ]
        style_alignment_notes = [
            "检查是否延续了原章克制推进、资源受限、逐步转强的节奏。",
            "检查是否避免了直接抄写原文表达。",
        ]
        risk_alignment_notes = [
            "重点复核角色动机/关系变化是否需要更多支撑。",
            "重点复核剧情推进是否存在 resolution/transition support gap。",
        ]
        verdict = "aligned" if draft.draft_text.strip() else "needs_review"
        return ChapterImitationComparisonReport(
            source_chapter_index=source_chapter_index,
            original_title=title,
            draft_title=draft.draft_title,
            source_length=len(source_text),
            draft_length=len(draft.draft_text),
            structure_overlap_notes=structure_overlap_notes,
            style_alignment_notes=style_alignment_notes,
            risk_alignment_notes=risk_alignment_notes,
            overall_verdict=verdict,
        )

    def review_draft(
        self,
        branch_id: str,
        *,
        source_chapter_index: int,
        draft: ChapterImitationDraft,
    ) -> ChapterImitationReviewReport:
        report = self.compare_with_source(
            branch_id,
            source_chapter_index=source_chapter_index,
            draft=draft,
        )
        _, source_text = self._source_chapter_text(branch_id, source_chapter_index)
        quality_notes = []
        if len(draft.draft_text) < max(200, len(source_text) // 6):
            quality_notes.append("草案偏短，可能只保留了骨架，信息密度仍不足。")
        if draft.original_title != draft.draft_title:
            quality_notes.append("标题已发生变化，需确认是否符合仿写目标。")
        risk_notes = list(draft.risk_gate_notes)
        revision_directions = [
            "优先补足与原章对应的中段阻力与行动转向，不要只保留开头与结尾。",
            "继续约束角色反应，避免把克制型推进写成情绪化爆发。",
            "如涉及关系变化，补足中间证据，不要只写结果。",
        ]
        needs_human_review = True
        overall_verdict = "aligned_but_needs_revision" if report.overall_verdict == "aligned" else "needs_revision"
        return ChapterImitationReviewReport(
            source_chapter_index=source_chapter_index,
            original_title=report.original_title,
            draft_title=report.draft_title,
            needs_human_review=needs_human_review,
            quality_gate_notes=quality_notes,
            risk_gate_notes=risk_notes,
            revision_directions=revision_directions,
            overall_verdict=overall_verdict,
        )

    def gate_draft(
        self,
        branch_id: str,
        *,
        source_chapter_index: int,
        draft: ChapterImitationDraft,
    ) -> ChapterImitationGateReport:
        _title, source_text = self._source_chapter_text(branch_id, source_chapter_index)
        synthetic_output = ChapterAnalysisOutput(
            chapter_index=source_chapter_index,
            normalized_title=draft.draft_title,
            chapter_summary=draft.draft_text[:200],
            key_entities=[],
            key_events=[],
            continuity_notes=draft.comparison_notes[:3],
            unsupported_inferences=[],
            ambiguous_points=[],
            needs_human_review=False,
        )
        quality = QualityGateService.evaluate(source_text, synthetic_output)
        risk_notes = list(draft.risk_gate_notes)
        if "直接抄原文" in draft.draft_text:
            risk_notes.append("检测到疑似直接复用原文措辞，需继续改写。")
        verdict = "aligned_but_needs_revision" if not quality.needs_human_review else "needs_revision"
        return ChapterImitationGateReport(
            source_chapter_index=source_chapter_index,
            draft_title=draft.draft_title,
            quality_gate_notes=quality.notes,
            needs_human_review=quality.needs_human_review,
            hook_score=quality.hook_score,
            risk_gate_notes=risk_notes,
            overall_verdict=verdict,
        )

    def risk_review_draft(
        self,
        branch_id: str,
        *,
        source_chapter_index: int,
        draft: ChapterImitationDraft,
    ) -> ChapterImitationRiskReport:
        artifact_payload = {
            "chapter_index": source_chapter_index,
            "normalized_title": draft.draft_title,
            "chapter_summary": draft.draft_text[:200],
            "key_entities": [],
            "key_events": [],
            "continuity_notes": draft.comparison_notes[:3],
            "state_transition_notes": draft.comparison_notes[:3],
            "evidence_backed_resolutions": [],
            "unresolved_threads": draft.risk_gate_notes[:3],
            "needs_human_review": True,
            "unsupported_inferences": [],
            "ambiguous_points": [],
        }
        results = []
        service = RiskAuditService(self.session)
        for checker in service.checkers:
            try:
                result = checker.evaluate(
                    branch_id=branch_id,
                    chapter_index=source_chapter_index,
                    artifact_payload=artifact_payload,
                    facts=[],
                )
            except Exception as exc:  # noqa: BLE001
                result = service.aggregate(  # type: ignore[assignment]
                    branch_id=branch_id,
                    chapter_index=source_chapter_index,
                    checker_results=[],
                )
                raise exc
            results.append(result)
        card = ChapterRiskCard.model_validate(
            RiskAuditService.aggregate(
                branch_id=branch_id,
                chapter_index=source_chapter_index,
                checker_results=results,
            ).model_dump(mode="json")
        )
        return ChapterImitationRiskReport(
            source_chapter_index=source_chapter_index,
            draft_title=draft.draft_title,
            overall_risk_level=card.overall_risk_level,
            checker_statuses=card.checker_statuses,
            top_risk_types=[item.risk_type for item in card.top_risks],
            top_risk_summaries=[item.summary for item in card.top_risks],
            coverage_gaps=card.coverage_gaps,
        )

    def revise_draft(
        self,
        draft: ChapterImitationDraft,
        *,
        review: ChapterImitationReviewReport,
    ) -> ChapterImitationDraft:
        revision_notes = list(draft.method_notes) + review.revision_directions
        revised_text = draft.draft_text
        if "草案偏短" in " ".join(review.quality_gate_notes):
            revised_text += "\n\n【修订提示】后续版本应补足中段阻力、行动抉择与章尾钩子之间的承接。"
        return ChapterImitationDraft(
            source_chapter_index=draft.source_chapter_index,
            original_title=draft.original_title,
            draft_title=draft.draft_title,
            draft_text=revised_text,
            method_notes=revision_notes,
            comparison_notes=draft.comparison_notes,
            risk_gate_notes=draft.risk_gate_notes + review.risk_gate_notes,
        )

    def score_draft(
        self,
        *,
        source_chapter_index: int,
        draft: ChapterImitationDraft,
        comparison: ChapterImitationComparisonReport,
        gate: ChapterImitationGateReport,
        risk: ChapterImitationRiskReport,
    ) -> ChapterImitationScoreReport:
        structure_score = 90 if comparison.overall_verdict == "aligned" else 65
        style_alignment_score = 70
        draft_length = len(draft.draft_text)
        if draft_length < 400:
            style_alignment_score -= 15
        if draft_length > 2400:
            style_alignment_score -= 5
        risk_score = 85 if risk.overall_risk_level == "low" else 60
        if gate.needs_human_review:
            risk_score -= 10
        overall_score = max(0, min(100, round((structure_score * 0.45) + (style_alignment_score * 0.25) + (risk_score * 0.30))))
        notes = [
            f"structure_score={structure_score}",
            f"style_alignment_score={style_alignment_score}",
            f"risk_score={risk_score}",
        ]
        return ChapterImitationScoreReport(
            source_chapter_index=source_chapter_index,
            draft_title=draft.draft_title,
            structure_score=structure_score,
            style_alignment_score=style_alignment_score,
            risk_score=risk_score,
            overall_score=overall_score,
            notes=notes,
        )

    def iterate_draft(
        self,
        branch_id: str,
        *,
        source_chapter_index: int,
        target_goal: str,
        max_rounds: int = 2,
        use_llm: bool = False,
        model_name: str | None = None,
    ) -> ChapterImitationIterationReport:
        rounds: list[ChapterImitationIterationRound] = []
        draft = (
            self.build_llm_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                target_goal=target_goal,
                model_name=model_name,
            )
            if use_llm
            else self.build_skeleton_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                target_goal=target_goal,
            )
        )

        stop_reason = "max_rounds_reached"
        for round_index in range(1, max_rounds + 1):
            comparison = self.compare_with_source(
                branch_id,
                source_chapter_index=source_chapter_index,
                draft=draft,
            )
            review = self.review_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                draft=draft,
            )
            gate = self.gate_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                draft=draft,
            )
            risk = self.risk_review_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                draft=draft,
            )
            score = self.score_draft(
                source_chapter_index=source_chapter_index,
                draft=draft,
                comparison=comparison,
                gate=gate,
                risk=risk,
            )
            rounds.append(
                ChapterImitationIterationRound(
                    round_index=round_index,
                    draft=draft,
                    comparison=comparison,
                    review=review,
                    gate=gate,
                    risk=risk,
                    score=score,
                )
            )
            if (
                comparison.overall_verdict == "aligned"
                and gate.overall_verdict != "needs_revision"
                and risk.overall_risk_level == "low"
                and score.overall_score >= 80
            ):
                stop_reason = "quality_threshold_reached"
                break
            draft = self.revise_draft(draft, review=review)

        return ChapterImitationIterationReport(
            source_chapter_index=source_chapter_index,
            target_goal=target_goal,
            max_rounds=max_rounds,
            rounds=rounds,
            final_draft=draft,
            stop_reason=stop_reason,
        )

    def build_multi_chapter_consistency(
        self,
        branch_id: str,
        *,
        chapter_goals: list[tuple[int, str]],
        max_rounds: int = 1,
        use_llm: bool = False,
        model_name: str | None = None,
    ) -> MultiChapterImitationConsistencyReport:
        if not chapter_goals:
            raise ValueError("chapter_goals must not be empty")
        steps: list[MultiChapterImitationStep] = []
        continuity_notes: list[str] = []
        risk_notes: list[str] = []

        previous_excerpt = ""
        previous_goal = ""
        for chapter_index, goal in chapter_goals:
            report = self.iterate_draft(
                branch_id,
                source_chapter_index=chapter_index,
                target_goal=goal,
                max_rounds=max_rounds,
                use_llm=use_llm,
                model_name=model_name,
            )
            final_round = report.rounds[-1]
            scaffold_only = bool(getattr(report.final_draft, "is_scaffold_only", False))
            final_draft_excerpt = (
                "[scaffold-only fallback; not user-facing prose]"
                if scaffold_only
                else report.final_draft.draft_text[:240]
            )
            steps.append(
                MultiChapterImitationStep(
                    source_chapter_index=chapter_index,
                    target_goal=goal,
                    final_title=report.final_draft.draft_title,
                    final_draft_excerpt=final_draft_excerpt,
                    overall_score=final_round.score.overall_score,
                    overall_risk_level=final_round.risk.overall_risk_level,
                    stop_reason=report.stop_reason,
                )
            )
            if previous_excerpt:
                continuity_notes.append(
                    f"第{chapter_index-1}章到第{chapter_index}章需检查：上一章目标“{previous_goal}”与下一章目标“{goal}”是否形成连续推进。"
                )
            if final_round.risk.coverage_gaps:
                risk_notes.append(
                    f"第{chapter_index}章仍有 coverage_gaps：{'、'.join(final_round.risk.coverage_gaps[:3])}"
                )
            previous_excerpt = (
                "" if scaffold_only else report.final_draft.draft_text[:120]
            )
            previous_goal = goal

        verdict = "aligned" if all(step.overall_risk_level == "low" for step in steps) else "needs_review"
        return MultiChapterImitationConsistencyReport(
            branch_id=branch_id,
            start_chapter_index=chapter_goals[0][0],
            end_chapter_index=chapter_goals[-1][0],
            steps=steps,
            continuity_notes=continuity_notes,
            risk_notes=risk_notes,
            overall_verdict=verdict,
        )

    @staticmethod
    def _extract_json_payload(raw_content: object) -> dict[str, object]:
        text = str(raw_content).strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        import json

        return json.loads(text)

    @staticmethod
    def _render_skeleton_text(*, title: str, plan: ChapterImitationPlan) -> str:
        lines = [f"第{plan.source_chapter_index}章 {title}", ""]
        lines.append(f"【章节目标】{plan.target_goal}")
        lines.append("")
        for idx, beat in enumerate(plan.scene_beats, start=1):
            lines.append(f"场景{idx}：{beat}")
        lines.append("")
        if plan.hard_constraints:
            lines.append("【硬约束】")
            for item in plan.hard_constraints:
                lines.append(f"- {item}")
        if plan.soft_constraints:
            lines.append("【软约束】")
            for item in plan.soft_constraints:
                lines.append(f"- {item}")
        lines.append("")
        lines.append("【说明】当前为仿写结构草案，用于后续 LLM 扩写与风险门控，不直接作为最终正文。")
        return "\n".join(lines)
