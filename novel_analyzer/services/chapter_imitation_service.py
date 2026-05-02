"""Chapter imitation / continuation planning skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import ChapterSegment, NovelSource, RunBranch
from novel_analyzer.domain.schemas import (
    ChapterImitationDraft,
    ChapterImitationComparisonReport,
    ChapterImitationPlan,
    ChapterPlanningIntent,
)
from novel_analyzer.llm.client import build_chat_model
from novel_analyzer.llm.prompts import build_chapter_imitation_prompt
from novel_analyzer.services.next_chapter_planner_service import (
    NextChapterPlannerService,
    PlannerContextWindow,
)
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

    def build_imitation_plan(
        self,
        branch_id: str,
        *,
        source_chapter_index: int,
        target_goal: str,
        method: ChapterImitationMethod | None = None,
    ) -> ChapterImitationPlan:
        effective = method or ChapterImitationMethod()
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

        return ChapterImitationPlan(
            source_chapter_index=source_chapter_index,
            target_goal=target_goal,
            style_axes=style_axes,
            scene_beats=scene_beats,
            hard_constraints=context.world_rules[:5] + context.forbidden_moves[:3],
            soft_constraints=context.relationship_state_notes[:3] + context.unresolved_threads[:3],
            risk_focus=context.recent_risk_signals[:3],
        )

    def build_skeleton_draft(
        self,
        branch_id: str,
        *,
        source_chapter_index: int,
        target_goal: str,
        method: ChapterImitationMethod | None = None,
    ) -> ChapterImitationDraft:
        plan = self.build_imitation_plan(
            branch_id,
            source_chapter_index=source_chapter_index,
            target_goal=target_goal,
            method=method,
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
    ) -> ChapterImitationDraft:
        plan = self.build_imitation_plan(
            branch_id,
            source_chapter_index=source_chapter_index,
            target_goal=target_goal,
            method=method,
        )
        title, source_text = self._source_chapter_text(branch_id, source_chapter_index)
        prompt = build_chapter_imitation_prompt(
            source_chapter_index=source_chapter_index,
            source_title=title,
            source_excerpt=source_text[:2500],
            target_goal=target_goal,
            style_axes=plan.style_axes,
            scene_beats=plan.scene_beats,
            hard_constraints=plan.hard_constraints,
            soft_constraints=plan.soft_constraints,
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
