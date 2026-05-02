"""Next-chapter planning skeleton built on top of branch state."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ChapterArtifact, FactRecord, RunBranch
from novel_analyzer.domain.schemas import (
    ChapterPlanningCard,
    ChapterPlanningContext,
    ChapterPlanningIntent,
    ChapterPlanningScene,
)
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.run_service import RunService


@dataclass(frozen=True, slots=True)
class PlannerContextWindow:
    """Small helper to control recent context width."""

    recent_chapter_count: int = 5


class NextChapterPlannerService:
    """Build a constrained next-chapter planning card from branch state."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.run_service = RunService(session)
        self.graph_service = GraphService(session)

    def build_context(
        self,
        branch_id: str,
        *,
        intent: ChapterPlanningIntent,
        window: PlannerContextWindow | None = None,
    ) -> ChapterPlanningContext:
        branch = self.session.scalar(select(RunBranch).where(RunBranch.id == branch_id))
        if branch is None:
            raise ValueError(f"Unknown branch_id: {branch_id}")
        current_chapter_index = max(branch.fork_after_chapter_index, self._latest_completed_chapter(branch_id))
        next_chapter_index = current_chapter_index + 1
        effective_window = window or PlannerContextWindow()

        recent_artifacts = (
            self.session.scalars(
                select(ChapterArtifact)
                .where(ChapterArtifact.branch_id == branch_id)
                .where(ChapterArtifact.chapter_index <= current_chapter_index)
                .where(ChapterArtifact.artifact_type == "chapter_analysis")
                .where(ChapterArtifact.deleted_at.is_(None))
                .order_by(ChapterArtifact.chapter_index.desc())
                .limit(effective_window.recent_chapter_count)
            )
            .all()
        )
        recent_artifacts = list(reversed(recent_artifacts))
        recent_summaries = [self._chapter_summary(item.payload_json) for item in recent_artifacts]
        recent_risk_signals = [self._risk_signal_hint(item.payload_json) for item in recent_artifacts]

        state_snapshot = self.graph_service.reasoning_snapshot(branch_id)
        state_summary = GraphService.state_summary_from_snapshot(
            state_snapshot,
            chapter_index=current_chapter_index,
        )
        unresolved_threads = list(self._string_list(state_summary.get("open_threads", [])))
        active_conflicts = list(self._string_list(state_summary.get("active_conflicts", [])))
        relationship_state_notes = list(self._string_list(state_summary.get("relationship_edges", [])))
        world_rules = list(self._string_list(state_summary.get("world_rules", [])))

        active_characters = self._active_characters(branch_id, current_chapter_index)

        planning_notes = [
            f"current_chapter={current_chapter_index}",
            f"next_chapter={next_chapter_index}",
            f"intent_goal={intent.primary_goal}",
        ]
        if intent.preferred_tone:
            planning_notes.append(f"preferred_tone={intent.preferred_tone}")
        if intent.pace:
            planning_notes.append(f"pace={intent.pace}")

        return ChapterPlanningContext(
            branch_id=branch_id,
            current_chapter_index=current_chapter_index,
            next_chapter_index=next_chapter_index,
            recent_chapter_summaries=[item for item in recent_summaries if item],
            active_characters=active_characters,
            relationship_state_notes=relationship_state_notes,
            active_conflicts=active_conflicts,
            unresolved_threads=unresolved_threads,
            world_rules=world_rules,
            recent_risk_signals=[item for item in recent_risk_signals if item],
            forbidden_moves=intent.forbidden_moves,
            planning_notes=planning_notes,
        )

    def build_plan(
        self,
        branch_id: str,
        *,
        intent: ChapterPlanningIntent,
        window: PlannerContextWindow | None = None,
    ) -> ChapterPlanningCard:
        context = self.build_context(branch_id, intent=intent, window=window)
        chapter_goal = intent.primary_goal.strip() or "延续当前剧情主线"
        main_conflict = (
            context.active_conflicts[0]
            if context.active_conflicts
            else "围绕当前章节目标制造可验证推进，而不破坏既有规则"
        )
        secondary_conflicts = context.active_conflicts[1:3]
        required_progressions = context.unresolved_threads[:3] or context.recent_risk_signals[:2]
        scene_plan = self._default_scene_plan(context=context, intent=intent, main_conflict=main_conflict)

        return ChapterPlanningCard(
            branch_id=branch_id,
            next_chapter_index=context.next_chapter_index,
            chapter_goal=chapter_goal,
            main_conflict=main_conflict,
            secondary_conflicts=secondary_conflicts,
            required_progressions=required_progressions,
            scene_plan=scene_plan,
            character_movements=context.active_characters[:4],
            relationship_movements=context.relationship_state_notes[:3],
            foreshadow_to_touch=context.unresolved_threads[:3],
            rule_constraints=context.world_rules[:5],
            ending_hook=self._default_ending_hook(context, intent),
            risk_notes=self._default_risk_notes(context, intent),
        )

    def _latest_completed_chapter(self, branch_id: str) -> int:
        row = self.session.execute(
            select(ChapterArtifact.chapter_index)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.artifact_type == "chapter_analysis")
            .where(ChapterArtifact.deleted_at.is_(None))
            .order_by(ChapterArtifact.chapter_index.desc())
            .limit(1)
        ).scalar_one_or_none()
        return int(row or 0)

    @staticmethod
    def _chapter_summary(payload: dict[str, object]) -> str:
        summary = payload.get("chapter_summary")
        return str(summary).strip() if summary else ""

    @staticmethod
    def _risk_signal_hint(payload: dict[str, object]) -> str:
        notes = payload.get("continuity_notes", [])
        if isinstance(notes, list) and notes:
            first = notes[0]
            if isinstance(first, str):
                return first.strip()
        return ""

    def _active_characters(self, branch_id: str, current_chapter_index: int) -> list[str]:
        rows = self.session.scalars(
            select(FactRecord.label)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index <= current_chapter_index)
            .where(FactRecord.fact_type == "entity")
            .where(FactRecord.deleted_at.is_(None))
            .order_by(FactRecord.chapter_index.desc())
            .limit(20)
        ).all()
        deduped: list[str] = []
        seen: set[str] = set()
        for item in rows:
            text = str(item).strip()
            if text and text not in seen:
                seen.add(text)
                deduped.append(text)
        return deduped

    @staticmethod
    def _string_list(items: object) -> list[str]:
        if not isinstance(items, list):
            return []
        return [str(item).strip() for item in items if str(item).strip()]

    def _default_scene_plan(
        self,
        *,
        context: ChapterPlanningContext,
        intent: ChapterPlanningIntent,
        main_conflict: str,
    ) -> list[ChapterPlanningScene]:
        scene_1 = ChapterPlanningScene(
            scene_index=1,
            purpose="承接上一章结果并明确本章目标",
            must_include=context.recent_chapter_summaries[-1:] + [intent.primary_goal],
            risk_notes=context.forbidden_moves[:2],
        )
        scene_2 = ChapterPlanningScene(
            scene_index=2,
            purpose="推进主冲突并释放新的信息增量",
            must_include=[main_conflict] + context.unresolved_threads[:2],
            risk_notes=context.recent_risk_signals[:2],
        )
        scene_3 = ChapterPlanningScene(
            scene_index=3,
            purpose="收束局部结果并留出下一章钩子",
            must_include=context.world_rules[:2] + context.active_conflicts[:1],
            risk_notes=["避免无铺垫的大幅关系/战力跳变"],
        )
        return [scene_1, scene_2, scene_3]

    @staticmethod
    def _default_ending_hook(context: ChapterPlanningContext, intent: ChapterPlanningIntent) -> str:
        if context.unresolved_threads:
            return f"以未解线程“{context.unresolved_threads[0]}”制造下一章推进钩子。"
        if context.active_conflicts:
            return f"以冲突“{context.active_conflicts[0]}”的升级作为章尾钩子。"
        return f"围绕“{intent.primary_goal}”留下下一章必须回应的新信息。"

    @staticmethod
    def _default_risk_notes(context: ChapterPlanningContext, intent: ChapterPlanningIntent) -> list[str]:
        notes = [
            "不要直接违背既有世界规则与人物当前状态。",
            "如要推进关系变化，必须提供中间证据与触发事件。",
        ]
        notes.extend(f"禁止：{item}" for item in intent.forbidden_moves[:3])
        notes.extend(f"风险信号：{item}" for item in context.recent_risk_signals[:3])
        return notes
