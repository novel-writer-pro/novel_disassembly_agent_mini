"""Whole-book imitation orchestration skeleton."""

from __future__ import annotations

from sqlalchemy.orm import Session

from novel_analyzer.domain.schemas import (
    StoryMappingPack,
    WholeBookCarryOverState,
    WholeBookImitationExecutedStep,
    WholeBookImitationPlan,
    WholeBookImitationQueueStep,
    WholeBookImitationRunReport,
)
from novel_analyzer.services.chapter_imitation_service import ChapterImitationService
from novel_analyzer.services.imitation_harness_service import HarnessControllerService


class WholeBookImitationService:
    """Compose chapter-level imitation into a whole-book planning skeleton."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.chapter_imitation = ChapterImitationService(session)
        self.harness = HarnessControllerService(session)

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
            execution_mode="dry_run",
            run_notes=run_notes,
        )

    def run_in_sandbox(
        self,
        branch_id: str,
        *,
        mapping_pack: StoryMappingPack,
        chapter_goals: list[tuple[int, str]],
        max_rounds: int = 1,
        use_llm: bool = False,
        model_name: str | None = None,
    ) -> WholeBookImitationRunReport:
        report = self.build_run_queue(
            branch_id,
            mapping_pack=mapping_pack,
            chapter_goals=chapter_goals,
        )
        executed_steps: list[WholeBookImitationExecutedStep] = []
        carry_state: WholeBookCarryOverState | None = None

        for step in report.queue:
            target_goal = step.target_goal
            if carry_state is not None:
                inherited_parts = [
                    item
                    for item in [
                        carry_state.generated_summary.strip(),
                        *carry_state.relationship_state[:2],
                        *carry_state.unresolved_threads[:2],
                        *carry_state.rule_state[:2],
                    ]
                    if item
                ]
                if inherited_parts:
                    target_goal = f"{target_goal}｜承接上一生成状态：{'；'.join(inherited_parts[:5])}"

            harness_report = self.harness.run_harness(
                branch_id,
                source_chapter_index=step.source_chapter_index,
                target_goal=target_goal,
                max_rounds=max_rounds,
                use_llm=use_llm,
                model_name=model_name,
            )
            final_round = harness_report.rounds[-1]
            carry_state = WholeBookCarryOverState(
                source_chapter_index=step.source_chapter_index,
                generated_summary=harness_report.final_draft.draft_text[:220],
                relationship_state=final_round.review.risk_gate_notes[:3],
                unresolved_threads=final_round.risk.top_risk_summaries[:3] or final_round.risk.coverage_gaps[:3],
                rule_state=final_round.risk.top_risk_types[:3],
                next_constraints=harness_report.final_draft.risk_gate_notes[:4],
            )
            executed_steps.append(
                WholeBookImitationExecutedStep(
                    order=step.order,
                    source_chapter_index=step.source_chapter_index,
                    target_goal=step.target_goal,
                    stop_reason=harness_report.stop_reason,
                    overall_score=final_round.score.overall_score,
                    overall_risk_level=final_round.risk.overall_risk_level,
                    draft_title=harness_report.final_draft.draft_title,
                    draft_excerpt=harness_report.final_draft.draft_text[:240],
                    carry_over_state=carry_state,
                    action_queue=harness_report.action_queue,
                    revise_payload=harness_report.rounds[-1].revise_payload if harness_report.rounds else {},
                    policy_summary=harness_report.policy_summary,
                )
            )

        run_notes = list(report.run_notes)
        run_notes.append("sandbox_execute 模式会逐章跑 iterate-imitation，并显式产出 carry-over state。")
        run_notes.append("当前仍是内存态 sandbox，不会把生成正文写入 live branch artifact。")
        highest_priority = min(
            (int(step.policy_summary.get("highest_action_priority", 4)) for step in executed_steps),
            default=4,
        )
        policy_summary = {
            "executed_step_count": len(executed_steps),
            "highest_action_priority": highest_priority,
            "max_overall_score": max((step.overall_score for step in executed_steps), default=0),
            "min_overall_score": min((step.overall_score for step in executed_steps), default=0),
            "risk_levels": [step.overall_risk_level for step in executed_steps],
            "stop_reasons": [step.stop_reason for step in executed_steps],
            "max_action_count": max((len(step.action_queue) for step in executed_steps), default=0),
            "verdicts": [str(step.policy_summary.get("final_verdict", "")) for step in executed_steps],
            "chapter_ranking": sorted(
                [
                    {
                        "source_chapter_index": step.source_chapter_index,
                        "overall_score": step.overall_score,
                        "highest_action_priority": int(step.policy_summary.get("highest_action_priority", 4)),
                    }
                    for step in executed_steps
                ],
                key=lambda item: (item["highest_action_priority"], item["overall_score"]),
            ),
            "severity_histogram": {
                "high": sum(1 for step in executed_steps for action in step.action_queue if action.severity == "high"),
                "medium": sum(1 for step in executed_steps for action in step.action_queue if action.severity == "medium"),
                "low": sum(1 for step in executed_steps for action in step.action_queue if action.severity == "low"),
            },
        }
        return WholeBookImitationRunReport(
            branch_id=report.branch_id,
            project_title=report.project_title,
            queue=report.queue,
            carry_over_notes=report.carry_over_notes,
            execution_mode="sandbox_execute",
            executed_steps=executed_steps,
            final_carry_over_state=carry_state,
            policy_summary=policy_summary,
            run_notes=run_notes,
        )
