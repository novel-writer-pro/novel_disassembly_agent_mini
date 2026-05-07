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
from novel_analyzer.services.author_knowledge_service import AuthorKnowledgeService
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
        self.author_knowledge_service = AuthorKnowledgeService(session)

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
        knowledge_pack = self.author_knowledge_service.build_branch_knowledge_pack(
            branch_id,
            upto_chapter_index=current_chapter_index,
            limit_per_section=12,
        )
        story_bible_pack = knowledge_pack.get("story_bible_pack", {}) if isinstance(knowledge_pack, dict) else {}
        volume_outline = story_bible_pack.get("volume_outline", {}) if isinstance(story_bible_pack, dict) else {}
        arc_outline = story_bible_pack.get("arc_outline", {}) if isinstance(story_bible_pack, dict) else {}
        future_chapter_outline = (
            story_bible_pack.get("future_chapter_outline", []) if isinstance(story_bible_pack, dict) else []
        )

        planning_notes = [
            f"current_chapter={current_chapter_index}",
            f"next_chapter={next_chapter_index}",
            f"intent_goal={intent.primary_goal}",
        ]
        if intent.preferred_tone:
            planning_notes.append(f"preferred_tone={intent.preferred_tone}")
        if intent.pace:
            planning_notes.append(f"pace={intent.pace}")
        volume_goal = str(volume_outline.get("volume_goal", "")).strip()
        if volume_goal:
            planning_notes.append(f"volume_goal={volume_goal}")
        for item in list(volume_outline.get("required_payoffs", []))[:2]:
            planning_notes.append(f"volume_payoff={item}")
        for item in list(arc_outline.get("payoff_targets", []))[:2]:
            planning_notes.append(f"arc_payoff={item}")
        for item in list(story_bible_pack.get("active_threads", []))[:2]:
            if str(item).strip() and str(item) not in unresolved_threads:
                unresolved_threads.append(str(item).strip())
        for item in future_chapter_outline[:2]:
            if not isinstance(item, dict):
                continue
            chapter_index = int(item.get("chapter_index", 0) or 0)
            goal = str(item.get("goal", "")).strip()
            conflict = str(item.get("core_conflict", "")).strip()
            payoff = str(item.get("payoff_target", "")).strip()
            turning = str(item.get("turning_point", "")).strip()
            if payoff and payoff not in unresolved_threads:
                unresolved_threads.append(payoff)
            if conflict and conflict not in active_conflicts:
                active_conflicts.append(conflict)
            if chapter_index and goal:
                encoded = f"chapter_outline:{chapter_index}:{goal}:{conflict}:{payoff}:{turning}"
                if encoded not in unresolved_threads:
                    unresolved_threads.append(encoded)

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
        story_signals = self._story_bible_signals(context)
        chapter_goal = story_signals.get("chapter_goal") or intent.primary_goal.strip() or "延续当前剧情主线"
        main_conflict = (
            context.active_conflicts[0]
            if context.active_conflicts
            else story_signals.get("main_conflict")
            or "围绕当前章节目标制造可验证推进，而不破坏既有规则"
        )
        secondary_conflicts = context.active_conflicts[1:3]
        required_progressions = context.unresolved_threads[:3] or context.recent_risk_signals[:2]
        for item in story_signals.get("required_progressions", []):
            if item not in required_progressions:
                required_progressions.append(item)
        scene_plan = self._default_scene_plan(
            context=context,
            intent=intent,
            main_conflict=main_conflict,
            story_signals=story_signals,
        )

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
            foreshadow_to_touch=required_progressions[:3],
            rule_constraints=context.world_rules[:5],
            ending_hook=self._default_ending_hook(context, intent, story_signals=story_signals),
            risk_notes=self._default_risk_notes(context, intent, story_signals=story_signals),
        )

    @staticmethod
    def _story_bible_signals(context: ChapterPlanningContext) -> dict[str, object]:
        notes = list(context.planning_notes)
        volume_goal = next((item.split("=", 1)[1] for item in notes if item.startswith("volume_goal=")), "")
        volume_payoffs = [item.split("=", 1)[1] for item in notes if item.startswith("volume_payoff=")]
        arc_payoffs = [item.split("=", 1)[1] for item in notes if item.startswith("arc_payoff=")]
        required_progressions = [item for item in volume_payoffs + arc_payoffs if item]
        main_conflict = ""
        if volume_goal:
            main_conflict = f"围绕“{volume_goal}”推进，并确保本章为后续兑现创造条件"
        chapter_goal = volume_goal or ""
        future_outline = []
        next_index = context.next_chapter_index
        for item in context.unresolved_threads:
            text = str(item).strip()
            if not text:
                continue
            if text.startswith("chapter_outline:"):
                parts = text.split(":", 5)
                if len(parts) >= 6:
                    try:
                        chapter_index = int(parts[1])
                    except ValueError:
                        continue
                    if chapter_index == next_index:
                        future_outline.append(
                            {
                                "chapter_index": chapter_index,
                                "goal": parts[2],
                                "core_conflict": parts[3],
                                "payoff_target": parts[4],
                                "turning_point": parts[5],
                            }
                        )
        if future_outline:
            first = future_outline[0]
            chapter_goal = str(first.get("goal") or chapter_goal or "")
            if str(first.get("core_conflict") or "").strip():
                main_conflict = str(first["core_conflict"])
            for key in ["payoff_target", "turning_point"]:
                value = str(first.get(key) or "").strip()
                if value and value not in required_progressions:
                    required_progressions.append(value)
        return {
            "chapter_goal": chapter_goal,
            "main_conflict": main_conflict,
            "required_progressions": required_progressions[:4],
            "future_outline": future_outline,
        }

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
        story_signals: dict[str, object] | None = None,
    ) -> list[ChapterPlanningScene]:
        story_signals = story_signals or {}
        future_outline = list(story_signals.get("future_outline", []))
        future_goal = ""
        future_turn = ""
        future_payoff = ""
        if future_outline:
            first = future_outline[0]
            future_goal = str(first.get("goal") or "").strip()
            future_turn = str(first.get("turning_point") or "").strip()
            future_payoff = str(first.get("payoff_target") or "").strip()
        scene_1 = ChapterPlanningScene(
            scene_index=1,
            purpose="承接上一章结果并明确本章目标",
            must_include=context.recent_chapter_summaries[-1:] + [future_goal or intent.primary_goal],
            risk_notes=context.forbidden_moves[:2] + ([future_turn] if future_turn else []),
        )
        scene_2 = ChapterPlanningScene(
            scene_index=2,
            purpose="推进主冲突并释放新的信息增量",
            must_include=[main_conflict] + ([future_payoff] if future_payoff else []) + context.unresolved_threads[:1],
            risk_notes=context.recent_risk_signals[:2],
        )
        scene_3 = ChapterPlanningScene(
            scene_index=3,
            purpose="收束局部结果并留出下一章钩子",
            must_include=([future_turn] if future_turn else []) + context.world_rules[:2] + context.active_conflicts[:1],
            risk_notes=["避免无铺垫的大幅关系/战力跳变"],
        )
        return [scene_1, scene_2, scene_3]

    @staticmethod
    def _default_ending_hook(
        context: ChapterPlanningContext,
        intent: ChapterPlanningIntent,
        *,
        story_signals: dict[str, object] | None = None,
    ) -> str:
        story_signals = story_signals or {}
        if story_signals.get("required_progressions"):
            first = list(story_signals.get("required_progressions", []))[0]
            return f"围绕长线兑现点“{first}”制造下一章推进钩子。"
        if context.unresolved_threads:
            return f"以未解线程“{context.unresolved_threads[0]}”制造下一章推进钩子。"
        if context.active_conflicts:
            return f"以冲突“{context.active_conflicts[0]}”的升级作为章尾钩子。"
        return f"围绕“{intent.primary_goal}”留下下一章必须回应的新信息。"

    @staticmethod
    def _default_risk_notes(
        context: ChapterPlanningContext,
        intent: ChapterPlanningIntent,
        *,
        story_signals: dict[str, object] | None = None,
    ) -> list[str]:
        story_signals = story_signals or {}
        notes = [
            "不要直接违背既有世界规则与人物当前状态。",
            "如要推进关系变化，必须提供中间证据与触发事件。",
        ]
        notes.extend(f"禁止：{item}" for item in intent.forbidden_moves[:3])
        notes.extend(f"长线兑现：{item}" for item in list(story_signals.get("required_progressions", []))[:2])
        notes.extend(f"风险信号：{item}" for item in context.recent_risk_signals[:3])
        return notes
