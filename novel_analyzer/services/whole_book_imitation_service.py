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

    @staticmethod
    def _strategy_input_from_revise_payload(previous_revise_payload: dict[str, object] | None) -> dict[str, object]:
        if not previous_revise_payload:
            return {}
        ordered = previous_revise_payload.get("ordered_actions", [])
        if not isinstance(ordered, list):
            return {}
        top_actions = [item for item in ordered[:3] if isinstance(item, dict)]
        return {
            "prioritized_targets": [str(item.get("target", "")) for item in top_actions if str(item.get("target", "")).strip()],
            "prioritized_action_types": [str(item.get("action_type", "")) for item in top_actions if str(item.get("action_type", "")).strip()],
            "prioritized_families": [str(item.get("issue_family", "")) for item in top_actions if str(item.get("issue_family", "")).strip()],
            "blocking_issues": previous_revise_payload.get("blocking_issues", []),
            "recommended_actions": previous_revise_payload.get("recommended_actions", []),
        }

    @staticmethod
    def _augment_strategy_input_with_policy(
        strategy_input: dict[str, object],
        previous_policy_summary: dict[str, object] | None,
    ) -> dict[str, object]:
        if not previous_policy_summary:
            return strategy_input
        issue_families = [
            str(item)
            for item in previous_policy_summary.get("issue_families", [])
            if str(item).strip()
        ]
        unique_families: list[str] = []
        seen: set[str] = set()
        for family in issue_families:
            if family not in seen:
                seen.add(family)
                unique_families.append(family)
        merged = dict(strategy_input)
        merged["prioritized_families"] = list(dict.fromkeys(
            [str(item) for item in strategy_input.get("prioritized_families", []) if str(item).strip()]
            + unique_families[:3]
        ))
        merged["priority_bias"] = int(previous_policy_summary.get("highest_action_priority", 4) or 4)
        merged["risk_bias"] = str(previous_policy_summary.get("risk_overall_level", "low") or "low")
        if merged["priority_bias"] <= 2 and unique_families:
            merged["recommended_actions"] = list(dict.fromkeys(
                [str(item) for item in strategy_input.get("recommended_actions", []) if str(item).strip()]
                + [f"优先处理上一章高优先级能力族：{'、'.join(unique_families[:2])}"]
            ))
        return merged

    @staticmethod
    def _augment_strategy_input_with_dashboard(
        strategy_input: dict[str, object],
        previous_dashboard_summary: dict[str, object] | None,
    ) -> dict[str, object]:
        if not previous_dashboard_summary:
            return strategy_input
        merged = dict(strategy_input)
        top_priority = previous_dashboard_summary.get("top_priority_summary", {})
        top_risk = previous_dashboard_summary.get("top_risk_summary", {})
        weak_families = [str(item) for item in top_priority.get("top_priority_families", []) if str(item).strip()]
        high_risk_families = [str(item) for item in top_risk.get("high_risk_families", []) if str(item).strip()]
        merged["prioritized_families"] = list(dict.fromkeys(
            [str(item) for item in strategy_input.get("prioritized_families", []) if str(item).strip()]
            + weak_families[:2]
            + high_risk_families[:2]
        ))
        if weak_families or high_risk_families:
            merged["recommended_actions"] = list(dict.fromkeys(
                [str(item) for item in strategy_input.get("recommended_actions", []) if str(item).strip()]
                + ([f"承接上一轮 top-priority families：{'、'.join(weak_families[:2])}"] if weak_families else [])
                + ([f"承接上一轮 top-risk families：{'、'.join(high_risk_families[:2])}"] if high_risk_families else [])
            ))
        return merged

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
        previous_revise_payload: dict[str, object] | None = None
        previous_policy_summary: dict[str, object] | None = None
        previous_dashboard_summary: dict[str, object] | None = None

        for step in report.queue:
            target_goal = step.target_goal
            strategy_input = self._strategy_input_from_revise_payload(previous_revise_payload)
            strategy_input = self._augment_strategy_input_with_policy(strategy_input, previous_policy_summary)
            strategy_input = self._augment_strategy_input_with_dashboard(strategy_input, previous_dashboard_summary)
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
            top_targets = strategy_input.get("prioritized_targets", [])
            if isinstance(top_targets, list) and top_targets:
                target_goal = f"{target_goal}｜优先处理上一章 revise targets：{'、'.join(top_targets[:2])}"
            top_families = strategy_input.get("prioritized_families", [])
            if isinstance(top_families, list) and top_families:
                target_goal = f"{target_goal}｜重点关注能力族：{'、'.join(top_families[:2])}"
            if int(strategy_input.get("priority_bias", 4) or 4) <= 2:
                target_goal = f"{target_goal}｜本章需优先响应上一章高优先级问题"
            if str(strategy_input.get("risk_bias", "low")) in {"medium", "high"}:
                target_goal = f"{target_goal}｜注意承接上一章的中高风险信号"

            harness_report = self.harness.run_harness(
                branch_id,
                source_chapter_index=step.source_chapter_index,
                target_goal=target_goal,
                max_rounds=max_rounds,
                use_llm=use_llm,
                model_name=model_name,
                strategy_input=strategy_input,
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
                    strategy_input=strategy_input,
                    policy_summary=harness_report.policy_summary,
                )
            )
            previous_revise_payload = harness_report.rounds[-1].revise_payload if harness_report.rounds else None
            previous_policy_summary = harness_report.policy_summary
            previous_dashboard_summary = {
                "top_priority_summary": {
                    "top_priority_families": [str(item) for item in harness_report.policy_summary.get("issue_families", []) if str(item).strip()][:3],
                },
                "top_risk_summary": {
                    "high_risk_families": [str(item) for item in harness_report.policy_summary.get("issue_families", []) if str(item).strip()][:3],
                },
            }

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
            "book_priority_ranking": sorted(
                [
                    {
                        "source_chapter_index": step.source_chapter_index,
                        "priority": int(step.policy_summary.get("highest_action_priority", 4)),
                        "severity": str(step.policy_summary.get("highest_action_severity", "low")),
                    }
                    for step in executed_steps
                ],
                key=lambda item: (item["priority"], item["source_chapter_index"]),
            ),
            "severity_histogram": {
                "high": sum(1 for step in executed_steps for action in step.action_queue if action.severity == "high"),
                "medium": sum(1 for step in executed_steps for action in step.action_queue if action.severity == "medium"),
                "low": sum(1 for step in executed_steps for action in step.action_queue if action.severity == "low"),
            },
            "risk_bucket_histogram": {
                "low": sum(1 for step in executed_steps if step.overall_risk_level == "low"),
                "medium": sum(1 for step in executed_steps if step.overall_risk_level == "medium"),
                "high": sum(1 for step in executed_steps if step.overall_risk_level == "high"),
            },
        }
        weak_family_counts = {
            "constraint": sum(1 for step in executed_steps for action in step.action_queue if "constraint" in action.action_type),
            "relationship": sum(1 for step in executed_steps for action in step.action_queue if "relationship" in action.action_type or "relation" in action.action_type),
            "rule": sum(1 for step in executed_steps for action in step.action_queue if "rule" in action.action_type),
            "motivation": sum(1 for step in executed_steps for action in step.action_queue if "motivation" in action.action_type),
            "hook": sum(1 for step in executed_steps for action in step.action_queue if "hook" in action.action_type),
            "dialogue": sum(1 for step in executed_steps for action in step.action_queue if "dialogue" in action.action_type),
            "research": sum(1 for step in executed_steps for action in step.action_queue if "research" in action.action_type),
            "rhythm": sum(1 for step in executed_steps for action in step.action_queue if "rhythm" in action.action_type),
            "reader": sum(1 for step in executed_steps for action in step.action_queue if "reader" in action.action_type),
        }
        weak_lane_counts = {
            "rhythm": sum(1 for step in executed_steps for action in step.action_queue if "rhythm" in action.action_type),
            "reader": sum(1 for step in executed_steps for action in step.action_queue if "reader" in action.action_type),
            "dialogue": sum(1 for step in executed_steps for action in step.action_queue if "dialogue" in action.action_type),
            "research": sum(1 for step in executed_steps for action in step.action_queue if "research" in action.action_type),
        }
        dashboard_summary = {
            "chapter_count": len(executed_steps),
            "highest_priority_chapters": [item["source_chapter_index"] for item in policy_summary["book_priority_ranking"][:3]],
            "top_risk_chapters": [
                step.source_chapter_index
                for step in executed_steps
                if step.overall_risk_level in {"medium", "high"}
            ],
            "strategy_targets": [
                {
                    "source_chapter_index": step.source_chapter_index,
                    "prioritized_targets": step.strategy_input.get("prioritized_targets", []),
                    "prioritized_families": step.strategy_input.get("prioritized_families", []),
                }
                for step in executed_steps
            ],
            "issue_family_histogram": {
                "constraint": weak_family_counts["constraint"],
                "relationship": weak_family_counts["relationship"],
                "rule": weak_family_counts["rule"],
                "motivation": weak_family_counts["motivation"],
                "hook": weak_family_counts["hook"],
                "dialogue": weak_family_counts["dialogue"],
                "research": weak_family_counts["research"],
            },
            "cluster_buckets": {
                "critical": [step.source_chapter_index for step in executed_steps if int(step.policy_summary.get("highest_action_priority", 4)) == 1],
                "attention": [step.source_chapter_index for step in executed_steps if int(step.policy_summary.get("highest_action_priority", 4)) == 2],
                "monitor": [step.source_chapter_index for step in executed_steps if int(step.policy_summary.get("highest_action_priority", 4)) >= 3],
            },
            "issue_family_ranking": sorted(
                [
                    {"family": family, "count": count}
                    for family, count in weak_family_counts.items()
                ],
                key=lambda item: (-item["count"], item["family"]),
            ),
            "weak_family_counts": weak_lane_counts,
            "family_priority_ranking": sorted(
                [
                    {
                        "source_chapter_index": step.source_chapter_index,
                        "families": step.strategy_input.get("prioritized_families", []),
                    }
                    for step in executed_steps
                ],
                key=lambda item: item["source_chapter_index"],
            ),
            "weak_lane_priority_ranking": sorted(
                [
                    {
                        "source_chapter_index": step.source_chapter_index,
                        "families": [
                            family
                            for family in step.strategy_input.get("prioritized_families", [])
                            if family in {"rhythm", "reader", "dialogue", "research"}
                        ],
                        "priority": int(step.policy_summary.get("highest_action_priority", 4)),
                    }
                    for step in executed_steps
                ],
                key=lambda item: (item["priority"], item["source_chapter_index"]),
            ),
            "top_weak_lane_chapters": [
                item["source_chapter_index"]
                for item in sorted(
                    [
                        {
                            "source_chapter_index": step.source_chapter_index,
                            "priority": int(step.policy_summary.get("highest_action_priority", 4)),
                            "weak_family_count": len(
                                [
                                    family
                                    for family in step.strategy_input.get("prioritized_families", [])
                                    if family in {"rhythm", "reader", "dialogue", "research"}
                                ]
                            ),
                        }
                        for step in executed_steps
                    ],
                    key=lambda item: (item["priority"], -item["weak_family_count"], item["source_chapter_index"]),
                )[:3]
            ],
            "weak_lane_histogram": {
                "rhythm": sum(1 for step in executed_steps for family in step.strategy_input.get("prioritized_families", []) if family == "rhythm"),
                "reader": sum(1 for step in executed_steps for family in step.strategy_input.get("prioritized_families", []) if family == "reader"),
                "dialogue": sum(1 for step in executed_steps for family in step.strategy_input.get("prioritized_families", []) if family == "dialogue"),
                "research": sum(1 for step in executed_steps for family in step.strategy_input.get("prioritized_families", []) if family == "research"),
            },
            "weak_lane_top_actions": [
                {
                    "source_chapter_index": step.source_chapter_index,
                    "action_type": action.action_type,
                    "priority": action.priority,
                    "severity": action.severity,
                }
                for step in executed_steps
                for action in step.action_queue
                if any(token in action.action_type for token in ("rhythm", "reader", "dialogue", "research"))
            ][:8],
            "top_priority_summary": {
                "chapter_indexes": [item["source_chapter_index"] for item in policy_summary["book_priority_ranking"][:3]],
                "weak_lane_chapters": [
                    item["source_chapter_index"]
                    for item in sorted(
                        [
                            {
                                "source_chapter_index": step.source_chapter_index,
                                "priority": int(step.policy_summary.get("highest_action_priority", 4)),
                                "weak_family_count": len(
                                    [
                                        family
                                        for family in step.strategy_input.get("prioritized_families", [])
                                        if family in {"rhythm", "reader", "dialogue", "research"}
                                    ]
                                ),
                            }
                            for step in executed_steps
                        ],
                        key=lambda item: (item["priority"], -item["weak_family_count"], item["source_chapter_index"]),
                    )[:3]
                ],
                "weak_lane_action_count": sum(int(step.policy_summary.get("weak_lane_action_count", 0)) for step in executed_steps),
                "top_priority_families": [
                    family
                    for family, count in sorted(
                        {
                            family: sum(
                                1
                                for step in executed_steps
                                for item in step.policy_summary.get("issue_families", [])
                                if str(item) == family and int(step.policy_summary.get("highest_action_priority", 4)) <= 2
                            )
                            for family in {"constraint", "relationship", "rule", "motivation", "hook", "dialogue", "research", "rhythm", "reader"}
                        }.items(),
                        key=lambda item: (-item[1], item[0]),
                    )
                    if count > 0
                ][:4],
            },
            "top_risk_summary": {
                "chapter_indexes": [
                    step.source_chapter_index
                    for step in executed_steps
                    if step.overall_risk_level in {"medium", "high"}
                ][:5],
                "weak_lane_actions": [
                    item
                    for item in [
                        {
                            "source_chapter_index": step.source_chapter_index,
                            "action_type": action.action_type,
                            "severity": action.severity,
                        }
                        for step in executed_steps
                        for action in step.action_queue
                        if action.severity in {"high", "medium"}
                        and any(token in action.action_type for token in ("rhythm", "reader", "dialogue", "research"))
                    ][:8]
                ],
                "weak_lane_families": [
                    family
                    for family, count in sorted(
                        weak_lane_counts.items(),
                        key=lambda item: (-item[1], item[0]),
                    )
                    if count > 0
                ][:4],
                "high_risk_families": [
                    family
                    for family, count in sorted(
                        {
                            family: sum(
                                1
                                for step in executed_steps
                                for action in step.action_queue
                                if step.overall_risk_level in {"medium", "high"}
                                and family in action.action_type
                            )
                            for family in {"rhythm", "reader", "dialogue", "research"}
                        }.items(),
                        key=lambda item: (-item[1], item[0]),
                    )
                    if count > 0
                ][:4],
            },
            "weak_lane_dominance": sorted(
                [
                    {"family": family, "count": count}
                    for family, count in {
                        "rhythm": sum(1 for step in executed_steps for family in step.strategy_input.get("prioritized_families", []) if family == "rhythm"),
                        "reader": sum(1 for step in executed_steps for family in step.strategy_input.get("prioritized_families", []) if family == "reader"),
                        "dialogue": sum(1 for step in executed_steps for family in step.strategy_input.get("prioritized_families", []) if family == "dialogue"),
                        "research": sum(1 for step in executed_steps for family in step.strategy_input.get("prioritized_families", []) if family == "research"),
                    }.items()
                ],
                key=lambda item: (-item["count"], item["family"]),
            ),
            "chapter_flags": [
                {
                    "source_chapter_index": step.source_chapter_index,
                    "highest_action_priority": int(step.policy_summary.get("highest_action_priority", 4)),
                    "overall_risk_level": step.overall_risk_level,
                    "weak_families": [
                        family
                        for family in step.strategy_input.get("prioritized_families", [])
                        if family in {"rhythm", "reader", "dialogue", "research"}
                    ],
                }
                for step in executed_steps
            ],
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
            dashboard_summary=dashboard_summary,
            run_notes=run_notes,
        )
