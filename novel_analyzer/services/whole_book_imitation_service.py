"""Whole-book imitation orchestration skeleton."""

from __future__ import annotations

from sqlalchemy.orm import Session

from novel_analyzer.domain.schemas import (
    StoryMappingPack,
    WholeBookImitationPlan,
    WholeBookImitationQueueStep,
    WholeBookImitationRunReport,
)
from novel_analyzer.services.chapter_imitation_service import ChapterImitationService


class WholeBookImitationService:
    """Compose chapter-level imitation into a whole-book planning skeleton."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.chapter_imitation = ChapterImitationService(session)

    def build_plan(
        self,
        branch_id: str,
        *,
        mapping_pack: StoryMappingPack,
        chapter_goals: list[tuple[int, str]],
    ) -> WholeBookImitationPlan:
        if not chapter_goals:
            raise ValueError("chapter_goals must not be empty")

        continuity_focus: list[str] = []
        orchestration_notes = [
            "先按章节目标逐章生成 draft，再做多章连续性校验。",
            "任何设定替换都必须优先通过 mapping_pack，而不是直接自由改写。",
            "在整本仿写阶段，单章风险低并不代表跨章关系/规则稳定，需要额外 continuity pass。",
        ]
        for idx, (_, goal) in enumerate(chapter_goals, start=1):
            continuity_focus.append(f"chapter_goal_{idx}={goal}")

        return WholeBookImitationPlan(
            branch_id=branch_id,
            project_title=mapping_pack.project_title,
            source_chapter_range=[item[0] for item in chapter_goals],
            mapping_pack=mapping_pack,
            chapter_goals=chapter_goals,
            continuity_focus=continuity_focus,
            orchestration_notes=orchestration_notes,
        )

    def build_run_queue(
        self,
        branch_id: str,
        *,
        mapping_pack: StoryMappingPack,
        chapter_goals: list[tuple[int, str]],
    ) -> WholeBookImitationRunReport:
        plan = self.build_plan(
            branch_id,
            mapping_pack=mapping_pack,
            chapter_goals=chapter_goals,
        )
        queue: list[WholeBookImitationQueueStep] = []
        carry_over_notes: list[str] = []

        previous_label: str | None = None
        previous_goal: str | None = None
        for order, (chapter_index, goal) in enumerate(chapter_goals, start=1):
            prerequisites = []
            carry_over_inputs: dict[str, list[str]] = {}
            if previous_label is not None:
                prerequisites.append(f"完成上一章节仿写并确认 carry-over：{previous_label}")
                carry_over_notes.append(
                    f"第{chapter_index}章生成前，应继承上一生成章节的关系/规则/未解线程快照。"
                )
                carry_over_inputs = {
                    "previous_generated_summary": [f"{previous_label} 的 final draft 摘要"],
                    "previous_generated_relationship_state": [f"{previous_label} 的关系推进结果"],
                    "previous_generated_unresolved_threads": [f"{previous_label} 遗留的未解线程"],
                    "previous_generated_rule_state": [f"{previous_label} 形成的规则/约束变化"],
                    "previous_goal": [previous_goal or ""],
                }
            queue.append(
                WholeBookImitationQueueStep(
                    order=order,
                    source_chapter_index=chapter_index,
                    target_goal=goal,
                    prerequisites=prerequisites,
                    carry_over_inputs=carry_over_inputs,
                    expected_outputs=[
                        "chapter plan",
                        "imitation draft",
                        "comparison report",
                        "review/gate/risk report",
                        "revised draft",
                    ],
                    risk_focus=[
                        "character_ooc",
                        "plot_logic_consistency",
                        "world_rule_consistency",
                    ],
                )
            )
            previous_label = f"第{chapter_index}章"
            previous_goal = goal

        run_notes = [
            "当前 whole-book runner 仍为 dry-run queue skeleton，不直接长跑整本生成。",
            "后续应把 queue step 接入 sandbox branch / draft artifact / continuity carry-over。",
        ]
        return WholeBookImitationRunReport(
            branch_id=branch_id,
            project_title=plan.project_title,
            queue=queue,
            carry_over_notes=carry_over_notes,
            run_notes=run_notes,
        )
