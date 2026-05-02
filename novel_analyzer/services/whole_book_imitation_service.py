"""Whole-book imitation orchestration skeleton."""

from __future__ import annotations

from sqlalchemy.orm import Session

from novel_analyzer.domain.schemas import (
    StoryMappingPack,
    WholeBookImitationPlan,
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
