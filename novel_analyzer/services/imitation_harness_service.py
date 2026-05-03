"""Controlled imitation harness with skill contracts and deterministic preflight checks."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.domain.schemas import (
    ChapterImitationComparisonReport,
    ChapterImitationDraft,
    ChapterImitationGateReport,
    ChapterImitationHarnessAction,
    ChapterImitationHarnessReport,
    ChapterImitationHarnessRound,
    ChapterImitationPreflightCheck,
    ChapterImitationPreflightReport,
    ChapterImitationReviewReport,
    ChapterImitationRiskReport,
    ChapterImitationScoreReport,
    ChapterImitationSkillContract,
    ChapterPlanningIntent,
)
from novel_analyzer.skills.assets import render_skill_prompt
from novel_analyzer.services.chapter_imitation_service import ChapterImitationService
from novel_analyzer.services.next_chapter_planner_service import PlannerContextWindow


class HarnessControllerService:
    """Drive imitation generation via explicit contracts, preflight, and targeted revision routing."""

    IMITATION_SKILLS: tuple[tuple[str, str, list[str], list[str]], ...] = (
        (
            "chapter-intake",
            "规范化源章节，保留原文结构输入。",
            ["chapter_index", "normalized_title", "chapter_content"],
            ["cleaned_text", "paragraph_blocks", "scene_candidates", "notes"],
        ),
        (
            "chapter-fact-extractor",
            "提取源章节事实层，为约束与 continuity 提供证据。",
            ["cleaned_text", "prior_context_json", "graph_context_json", "state_summary_json"],
            ["characters", "events", "relations", "conflicts", "foreshadowing", "worldbuilding_facts"],
        ),
        (
            "imitation-constraint-pack",
            "汇总人物/规则/关系/线程约束，形成 imitation memory pack。",
            ["source_plan", "branch_context", "mapping_pack", "carry_over_state"],
            ["hard_constraints", "soft_constraints", "forbidden_transformations", "continuity_memory"],
        ),
        (
            "draft-writer",
            "按结构目标与约束产出 draft。",
            ["source_plan", "constraint_pack", "target_goal"],
            ["draft_title", "draft_text", "method_notes", "risk_gate_notes"],
        ),
        (
            "draft-self-check",
            "先行识别 likely gate failures，减少正式审查链浪费。",
            ["draft_text", "source_plan", "constraint_pack"],
            ["blocking_issues", "recommended_actions", "self_notes"],
        ),
        (
            "rhythm-analyzer",
            "分析章节节奏、场景密度、钩子强度与张力起伏。",
            ["draft_text", "scene_plan", "chapter_goal"],
            ["pace_label", "hook_strength", "tension_curve", "issues", "recommended_actions"],
        ),
        (
            "reader-sim-review",
            "模拟读者视角，给出清晰度、沉浸感、期待感与疑虑点。",
            ["draft_text", "chapter_goal", "constraint_pack"],
            ["reader_profile", "engagement_score", "concerns", "recommended_actions"],
        ),
        (
            "dialogue-designer",
            "分析对话设计、说话人区分与信息效率。",
            ["draft_text", "chapter_goal", "relationship_context"],
            ["issues", "speaker_hints", "efficiency_notes", "recommended_actions"],
        ),
        (
            "research-pack",
            "补 setting / rule / audience expectation 研究提示。",
            ["chapter_goal", "world_context", "topic_hints"],
            ["setting_notes", "rule_reminders", "audience_expectation_notes", "caution_points"],
        ),
        (
            "draft-reviser",
            "按 harness 指定问题做局部修订，不自由扩散。",
            ["draft_text", "targeted_actions"],
            ["revised_draft_text", "revision_notes"],
        ),
    )

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.chapter_imitation = ChapterImitationService(session, self.settings)

    @staticmethod
    def _severity_priority(status: str, *, risk_level: str | None = None) -> tuple[str, int]:
        if status == "block":
            return ("high", 1)
        if risk_level == "high":
            return ("high", 1)
        if risk_level == "medium":
            return ("medium", 2)
        if status == "warn":
            return ("medium", 2)
        return ("low", 4)

    @staticmethod
    def _issue_family_for_action(action_type: str) -> str:
        lowered = action_type.lower()
        if "constraint" in lowered:
            return "constraint"
        if "relationship" in lowered or "relation" in lowered:
            return "relationship"
        if "rule" in lowered:
            return "rule"
        if "motivation" in lowered:
            return "motivation"
        if "hook" in lowered:
            return "hook"
        if "rhythm" in lowered:
            return "rhythm"
        if "reader" in lowered:
            return "reader"
        if "dialogue" in lowered:
            return "dialogue"
        if "research" in lowered:
            return "research"
        return "general"

    @staticmethod
    def _sorted_actions(actions: list[ChapterImitationHarnessAction]) -> list[ChapterImitationHarnessAction]:
        return sorted(actions, key=lambda item: (item.priority, item.action_type, item.target))

    @staticmethod
    def _aggregate_stop_reason(
        *,
        preflight: ChapterImitationPreflightReport,
        gate: ChapterImitationGateReport,
        risk: ChapterImitationRiskReport,
        score: ChapterImitationScoreReport,
        actions: list[ChapterImitationHarnessAction],
    ) -> tuple[str, str]:
        if preflight.overall_verdict == "pass" and gate.overall_verdict != "needs_revision" and risk.overall_risk_level == "low" and score.overall_score >= 80:
            return ("pass", "harness_quality_threshold_reached")
        if any(item.priority == 1 for item in actions):
            return ("needs_revision", "critical_action_required")
        if risk.overall_risk_level != "low":
            return ("needs_revision", "risk_revision_required")
        if gate.overall_verdict == "needs_revision":
            return ("needs_revision", "gate_revision_required")
        return ("needs_revision", "quality_iteration_required")

    @staticmethod
    def _apply_actions_to_draft(
        draft: ChapterImitationDraft,
        *,
        review: ChapterImitationReviewReport,
        preflight: ChapterImitationPreflightReport,
        actions: list[ChapterImitationHarnessAction],
        base_reviser,
    ) -> ChapterImitationDraft:
        revised = base_reviser(draft, review=review)
        action_lines = [f"[P{item.priority}|{item.severity}] {item.action_type}:{item.target}" for item in actions[:6]]
        revise_notes = [
            "【Harness Action Queue】",
            *action_lines,
        ]
        revise_payload = HarnessControllerService._build_revise_payload(
            actions=actions,
            preflight=preflight,
            gate=ChapterImitationGateReport(source_chapter_index=draft.source_chapter_index, draft_title=draft.draft_title),
            risk=ChapterImitationRiskReport(source_chapter_index=draft.source_chapter_index, draft_title=draft.draft_title),
        )
        return revised.model_copy(
            update={
                "risk_gate_notes": revised.risk_gate_notes + preflight.recommended_actions[:3],
                "method_notes": revised.method_notes + [f"{item.priority}:{item.target}" for item in actions],
                "comparison_notes": revised.comparison_notes + [f"ACTION:{item.action_type}:{item.target}" for item in actions[:4]] + [json.dumps(revise_payload, ensure_ascii=False)[:300]],
                "draft_text": revised.draft_text + ("\n\n" + "\n".join(revise_notes) if action_lines else ""),
            }
        )

    @staticmethod
    def _policy_summary(
        *,
        preflight: ChapterImitationPreflightReport,
        gate: ChapterImitationGateReport,
        risk: ChapterImitationRiskReport,
        score: ChapterImitationScoreReport,
        actions: list[ChapterImitationHarnessAction],
        final_verdict: str,
        stop_reason: str,
    ) -> dict[str, object]:
        highest_priority = min((item.priority for item in actions), default=4)
        highest_severity = "low"
        for item in actions:
            if item.severity == "high":
                highest_severity = "high"
                break
            if item.severity == "medium":
                highest_severity = "medium"
        issue_families = [HarnessControllerService._issue_family_for_action(item.action_type) for item in actions]
        return {
            "final_verdict": final_verdict,
            "stop_reason": stop_reason,
            "highest_action_priority": highest_priority,
            "highest_action_severity": highest_severity,
            "action_count": len(actions),
            "blocking_issue_count": len(preflight.blocking_issues),
            "recommended_action_count": len(preflight.recommended_actions),
            "gate_verdict": gate.overall_verdict,
            "risk_overall_level": risk.overall_risk_level,
            "overall_score": score.overall_score,
            "issue_families": issue_families,
        }

    @staticmethod
    def _build_revise_payload(
        *,
        actions: list[ChapterImitationHarnessAction],
        preflight: ChapterImitationPreflightReport,
        gate: ChapterImitationGateReport,
        risk: ChapterImitationRiskReport,
    ) -> dict[str, object]:
        return {
            "ordered_actions": [
                {
                    "action_type": item.action_type,
                    "issue_family": HarnessControllerService._issue_family_for_action(item.action_type),
                    "target": item.target,
                    "severity": item.severity,
                    "priority": item.priority,
                    "instructions": item.instructions,
                }
                for item in actions
            ],
            "blocking_issues": preflight.blocking_issues,
            "recommended_actions": preflight.recommended_actions,
            "gate_verdict": gate.overall_verdict,
            "risk_overall_level": risk.overall_risk_level,
            "issue_families": [
                HarnessControllerService._issue_family_for_action(item.action_type)
                for item in actions
            ],
        }

    def list_skill_contracts(self) -> list[ChapterImitationSkillContract]:
        root = Path(self.settings.skills_dir)
        contracts: list[ChapterImitationSkillContract] = []
        for skill_name, purpose, required_inputs, produced_outputs in self.IMITATION_SKILLS:
            prompt_asset = root / skill_name / "prompts" / "main.md"
            schema_asset = root / skill_name / "schemas" / "output.schema.json"
            prompt_preview = ""
            if prompt_asset.exists():
                prompt_preview = prompt_asset.read_text(encoding="utf-8")[:180]
            contracts.append(
                ChapterImitationSkillContract(
                    skill_name=skill_name,
                    purpose=purpose,
                    required_inputs=required_inputs,
                    produced_outputs=produced_outputs,
                    prompt_asset_path=str(prompt_asset),
                    schema_asset_path=str(schema_asset),
                    prompt_preview=prompt_preview,
                )
            )
        return contracts

    def preflight_draft(
        self,
        branch_id: str,
        *,
        source_chapter_index: int,
        draft: ChapterImitationDraft,
        comparison: ChapterImitationComparisonReport | None = None,
        skill_outputs: dict[str, dict[str, object]] | None = None,
    ) -> ChapterImitationPreflightReport:
        compare = comparison or self.chapter_imitation.compare_with_source(
            branch_id,
            source_chapter_index=source_chapter_index,
            draft=draft,
        )
        outputs = skill_outputs or {}
        checks: list[ChapterImitationPreflightCheck] = []
        blocking_issues: list[str] = []
        recommended_actions: list[str] = []

        source_length = max(compare.source_length, 1)
        draft_length = compare.draft_length
        length_ratio = draft_length / source_length
        if length_ratio < 0.18:
            blocking_issues.append("draft_too_short_for_gate")
            recommended_actions.append("补足中段阻力、行动转向与章尾钩子之间的承接。")
            checks.append(
                ChapterImitationPreflightCheck(
                    check_name="length_ratio",
                    status="block",
                    severity="high",
                    priority=1,
                    notes=[f"draft/source 长度比过低：{length_ratio:.2f}"],
                )
            )
        else:
            checks.append(
                ChapterImitationPreflightCheck(
                    check_name="length_ratio",
                    status="pass",
                    severity="low",
                    priority=4,
                    notes=[f"draft/source 长度比={length_ratio:.2f}"],
                )
            )

        if compare.overall_verdict != "aligned":
            blocking_issues.append("structure_alignment_failed")
            recommended_actions.append("回到 source skeleton，先修结构对齐再做 prose 优化。")
            checks.append(
                ChapterImitationPreflightCheck(
                    check_name="structure_alignment",
                    status="block",
                    severity="high",
                    priority=1,
                    notes=["comparison.overall_verdict != aligned"],
                )
            )
        else:
            checks.append(
                ChapterImitationPreflightCheck(
                    check_name="structure_alignment",
                    status="pass",
                    severity="low",
                    priority=4,
                    notes=["source skeleton alignment looks acceptable"],
                )
            )

        direct_copy = "直接抄原文" in draft.draft_text
        if direct_copy:
            blocking_issues.append("possible_direct_copy")
            recommended_actions.append("改写表述，不要复用原章措辞。")
            checks.append(
                ChapterImitationPreflightCheck(
                    check_name="direct_copy_guard",
                    status="block",
                    severity="high",
                    priority=1,
                    notes=["检测到疑似直接抄原文信号。"],
                )
            )
        else:
            checks.append(
                ChapterImitationPreflightCheck(
                    check_name="direct_copy_guard",
                    status="pass",
                    severity="low",
                    priority=4,
                    notes=["未见直接抄写标记。"],
                )
            )

        hook_present = "钩子" in draft.draft_text or "下一步" in draft.draft_text or "接下来" in draft.draft_text
        if not hook_present:
            recommended_actions.append("补一个明确的下一步钩子，避免章节收束过平。")
            checks.append(
                ChapterImitationPreflightCheck(
                    check_name="ending_hook_presence",
                    status="warn",
                    severity="medium",
                    priority=3,
                    notes=["未检测到显式下一步钩子词。"],
                )
            )
        else:
            checks.append(
                ChapterImitationPreflightCheck(
                    check_name="ending_hook_presence",
                    status="pass",
                    severity="low",
                    priority=4,
                    notes=["检测到下一步/钩子相关收束。"],
                )
            )

        constraint_pack = outputs.get("imitation-constraint-pack", {})
        if isinstance(constraint_pack, dict):
            forbidden = [str(item) for item in constraint_pack.get("forbidden_transformations", []) if str(item).strip()]
            relationship_watch = [str(item) for item in constraint_pack.get("relationship_watchpoints", []) if str(item).strip()]
            rule_watch = [str(item) for item in constraint_pack.get("rule_watchpoints", []) if str(item).strip()]
            if forbidden:
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="constraint_pack_presence",
                        status="pass",
                        severity="low",
                        priority=4,
                        notes=[f"forbidden_transformations={len(forbidden)}"],
                    )
                )
            else:
                recommended_actions.append("补齐 forbidden_transformations，明确哪些换皮/越界动作不能做。")
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="constraint_pack_presence",
                        status="warn",
                        severity="medium",
                        priority=2,
                        notes=["constraint pack 未给出明确 forbidden_transformations。"],
                    )
                )
            if relationship_watch:
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="relationship_watchpoints",
                        status="pass",
                        severity="low",
                        priority=4,
                        notes=relationship_watch[:3],
                    )
                )
            else:
                recommended_actions.append("补充 relationship_watchpoints，明确关系推进敏感点。")
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="relationship_watchpoints",
                        status="warn",
                        severity="medium",
                        priority=2,
                        notes=["constraint pack 缺少 relationship watchpoints。"],
                    )
                )
            if rule_watch:
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="rule_watchpoints",
                        status="pass",
                        severity="low",
                        priority=4,
                        notes=rule_watch[:3],
                    )
                )
            else:
                recommended_actions.append("补充 rule_watchpoints，明确世界规则敏感点。")
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="rule_watchpoints",
                        status="warn",
                        severity="medium",
                        priority=2,
                        notes=["constraint pack 缺少 rule watchpoints。"],
                    )
                )

        self_check = outputs.get("draft-self-check", {})
        if isinstance(self_check, dict):
            predicted_blockers = [str(item) for item in self_check.get("blocking_issues", []) if str(item).strip()]
            predicted_actions = [str(item) for item in self_check.get("recommended_actions", []) if str(item).strip()]
            likely_failures = [str(item) for item in self_check.get("likely_gate_failures", []) if str(item).strip()]
            if predicted_blockers:
                blocking_issues.extend(item for item in predicted_blockers if item not in blocking_issues)
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="draft_self_check_blockers",
                        status="block",
                        severity="high",
                        priority=1,
                        notes=predicted_blockers[:3],
                    )
                )
            elif predicted_actions:
                recommended_actions.extend(item for item in predicted_actions if item not in recommended_actions)
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="draft_self_check_recommendations",
                        status="warn",
                        severity="medium",
                        priority=2,
                        notes=predicted_actions[:3],
                    )
                )
            else:
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="draft_self_check_recommendations",
                        status="pass",
                        severity="low",
                        priority=4,
                        notes=["draft-self-check 未返回阻断问题。"],
                    )
                )
            if likely_failures:
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="draft_self_check_likely_failures",
                        status="warn",
                        severity="medium",
                        priority=2,
                        notes=likely_failures[:3],
                    )
                )
                if "character_motivation_drift" in likely_failures:
                    recommended_actions.append("补足人物动机支撑，避免角色行为漂移。")
                if "relationship_transition_thin" in likely_failures:
                    recommended_actions.append("补足关系变化前后的中间证据。")
                if "world_rule_support_thin" in likely_failures:
                    recommended_actions.append("补足规则支撑，避免越界动作无来源。")
                if "ending_hook_presence" in likely_failures:
                    recommended_actions.append("补充更明确的章尾钩子。")

        chapter_intake = outputs.get("chapter-intake", {})
        if isinstance(chapter_intake, dict):
            intake_notes = [str(item) for item in chapter_intake.get("notes", []) if str(item).strip()]
            if intake_notes:
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="chapter_intake_notes",
                        status="pass",
                        severity="low",
                        priority=4,
                        notes=intake_notes[:3],
                    )
                )

        fact_output = outputs.get("chapter-fact-extractor", {})
        if isinstance(fact_output, dict):
            relation_count = len([item for item in fact_output.get("relations", []) if item])
            rule_count = len([item for item in fact_output.get("worldbuilding_facts", []) if item])
            if relation_count == 0:
                recommended_actions.append("补充关系证据，避免关系变化无中间支撑。")
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="fact_relation_coverage",
                        status="warn",
                        severity="medium",
                        priority=2,
                        notes=["chapter-fact-extractor 未提取到关系事实。"],
                    )
                )
            else:
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="fact_relation_coverage",
                        status="pass",
                        severity="low",
                        priority=4,
                        notes=[f"relations={relation_count}"],
                    )
                )
            if rule_count == 0:
                recommended_actions.append("补充规则证据，避免关键动作缺少世界规则支撑。")
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="fact_rule_coverage",
                        status="warn",
                        severity="medium",
                        priority=2,
                        notes=["chapter-fact-extractor 未提取到规则事实。"],
                    )
                )
            else:
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="fact_rule_coverage",
                        status="pass",
                        severity="low",
                        priority=4,
                        notes=[f"worldbuilding_facts={rule_count}"],
                    )
                )

        rhythm_output = outputs.get("rhythm-analyzer", {})
        if isinstance(rhythm_output, dict):
            issues = [str(item) for item in rhythm_output.get("issues", []) if str(item).strip()]
            actions = [str(item) for item in rhythm_output.get("recommended_actions", []) if str(item).strip()]
            hook_strength = float(rhythm_output.get("hook_strength", 0.0) or 0.0)
            if issues:
                recommended_actions.extend(item for item in actions if item not in recommended_actions)
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="rhythm_analysis",
                        status="warn",
                        severity="medium",
                        priority=2,
                        notes=issues[:3],
                    )
                )
            else:
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="rhythm_analysis",
                        status="pass",
                        severity="low",
                        priority=4,
                        notes=[f"hook_strength={hook_strength:.2f}"],
                    )
                )

        reader_output = outputs.get("reader-sim-review", {})
        if isinstance(reader_output, dict):
            concerns = [str(item) for item in reader_output.get("concerns", []) if str(item).strip()]
            actions = [str(item) for item in reader_output.get("recommended_actions", []) if str(item).strip()]
            if concerns:
                recommended_actions.extend(item for item in actions if item not in recommended_actions)
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="reader_sim_review",
                        status="warn",
                        severity="medium",
                        priority=3,
                        notes=concerns[:3],
                    )
                )
            else:
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="reader_sim_review",
                        status="pass",
                        severity="low",
                        priority=4,
                        notes=[f"engagement_score={reader_output.get('engagement_score', 0)}"],
                    )
                )

        dialogue_output = outputs.get("dialogue-designer", {})
        if isinstance(dialogue_output, dict):
            issues = [str(item) for item in dialogue_output.get("issues", []) if str(item).strip()]
            actions = [str(item) for item in dialogue_output.get("recommended_actions", []) if str(item).strip()]
            if issues:
                recommended_actions.extend(item for item in actions if item not in recommended_actions)
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="dialogue_designer",
                        status="warn",
                        severity="medium",
                        priority=3,
                        notes=issues[:3],
                    )
                )
            else:
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="dialogue_designer",
                        status="pass",
                        severity="low",
                        priority=4,
                        notes=[f"speaker_hints={len(dialogue_output.get('speaker_hints', []))}"],
                    )
                )

        research_output = outputs.get("research-pack", {})
        if isinstance(research_output, dict):
            cautions = [str(item) for item in research_output.get("caution_points", []) if str(item).strip()]
            audience_notes = [str(item) for item in research_output.get("audience_expectation_notes", []) if str(item).strip()]
            if cautions or audience_notes:
                recommended_actions.extend(item for item in cautions[:2] if item not in recommended_actions)
                recommended_actions.extend(item for item in audience_notes[:2] if item not in recommended_actions)
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="research_pack_review",
                        status="warn",
                        severity="medium",
                        priority=3,
                        notes=(cautions + audience_notes)[:3],
                    )
                )
            else:
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="research_pack_review",
                        status="pass",
                        severity="low",
                        priority=4,
                        notes=["research pack 未提示额外 caution。"],
                    )
                )

        if risk_level := getattr(outputs.get("_risk_meta", {}), "get", lambda *_: None)("overall_risk_level"):
            severity, priority = self._severity_priority("warn", risk_level=str(risk_level))
            checks.append(
                ChapterImitationPreflightCheck(
                    check_name="risk_gate_alignment",
                    status="warn" if str(risk_level) != "low" else "pass",
                    severity=severity,
                    priority=priority,
                    notes=[f"risk_overall_level={risk_level}"],
                )
            )

        if gate_verdict := getattr(outputs.get("_gate_meta", {}), "get", lambda *_: None)("overall_verdict"):
            if str(gate_verdict) == "needs_revision":
                recommended_actions.append("补足 quality gate 指出的章节问题后再继续。")
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="gate_alignment",
                        status="block",
                        severity="high",
                        priority=1,
                        notes=[f"gate_verdict={gate_verdict}"],
                    )
                )
                blocking_issues.append("gate_verdict_requires_revision")
            else:
                checks.append(
                    ChapterImitationPreflightCheck(
                        check_name="gate_alignment",
                        status="pass",
                        severity="low",
                        priority=4,
                        notes=[f"gate_verdict={gate_verdict}"],
                    )
                )

        verdict = "block" if blocking_issues else ("warn" if recommended_actions else "pass")
        return ChapterImitationPreflightReport(
            source_chapter_index=source_chapter_index,
            draft_title=draft.draft_title,
            overall_verdict=verdict,
            checks=checks,
            blocking_issues=blocking_issues,
            recommended_actions=recommended_actions,
        )

    def build_skill_prompt_previews(
        self,
        branch_id: str,
        *,
        source_chapter_index: int,
        target_goal: str,
        draft: ChapterImitationDraft,
    ) -> dict[str, str]:
        title, source_text = self.chapter_imitation._source_chapter_text(branch_id, source_chapter_index)  # noqa: SLF001
        plan = self.chapter_imitation.build_imitation_plan(
            branch_id,
            source_chapter_index=source_chapter_index,
            target_goal=target_goal,
        )
        planner_context = self.chapter_imitation.next_chapter_planner.build_context(
            branch_id,
            intent=ChapterPlanningIntent(
                primary_goal=target_goal,
                emphasis=["保持人物连续性", "保持冲突推进", "保持风格约束"],
                forbidden_moves=["不要无铺垫升级战力", "不要引入未准备的大设定"],
                preferred_tone="克制务实",
                pace="steady",
            ),
            window=PlannerContextWindow(recent_chapter_count=3),
        )
        compare = self.chapter_imitation.compare_with_source(
            branch_id,
            source_chapter_index=source_chapter_index,
            draft=draft,
        )
        payloads = {
            "imitation-constraint-pack": {
                "source_plan_json": json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2),
                "branch_context_json": json.dumps(planner_context.model_dump(mode="json"), ensure_ascii=False, indent=2),
                "mapping_pack_json": "{}",
                "carry_over_state_json": "{}",
            },
            "draft-self-check": {
                "draft_text": draft.draft_text,
                "source_plan_json": json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2),
                "constraint_pack_json": json.dumps(
                    {
                        "hard_constraints": plan.hard_constraints,
                        "soft_constraints": plan.soft_constraints,
                        "risk_focus": plan.risk_focus,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            },
            "rhythm-analyzer": {
                "draft_text": draft.draft_text,
                "scene_plan_json": json.dumps(plan.scene_beats, ensure_ascii=False, indent=2),
                "chapter_goal": target_goal,
            },
            "reader-sim-review": {
                "draft_text": draft.draft_text,
                "chapter_goal": target_goal,
                "constraint_pack_json": json.dumps(
                    {
                        "hard_constraints": plan.hard_constraints,
                        "soft_constraints": plan.soft_constraints,
                        "risk_focus": plan.risk_focus,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            },
            "dialogue-designer": {
                "draft_text": draft.draft_text,
                "chapter_goal": target_goal,
                "relationship_context_json": json.dumps(plan.soft_constraints[:4], ensure_ascii=False, indent=2),
            },
            "research-pack": {
                "chapter_goal": target_goal,
                "world_context_json": json.dumps(
                    {
                        "world_rules": plan.hard_constraints[:4],
                        "continuity_memory": plan.soft_constraints[:4],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                "topic_hints_json": json.dumps(plan.risk_focus[:3], ensure_ascii=False, indent=2),
            },
            "chapter-intake": {
                "chapter_index": str(source_chapter_index),
                "normalized_title": title,
                "previous_summary": planner_context.recent_chapter_summaries[-1] if planner_context.recent_chapter_summaries else "",
                "chapter_content": source_text[:2400],
            },
            "chapter-fact-extractor": {
                "chapter_index": str(source_chapter_index),
                "normalized_title": title,
                "cleaned_text": source_text[:2400],
                "prior_context_json": json.dumps(planner_context.recent_chapter_summaries[:2], ensure_ascii=False),
                "graph_context_json": json.dumps(planner_context.relationship_state_notes[:3], ensure_ascii=False),
                "state_summary_json": json.dumps(
                    {
                        "unresolved_threads": planner_context.unresolved_threads[:3],
                        "world_rules": planner_context.world_rules[:3],
                    },
                    ensure_ascii=False,
                ),
            },
        }
        previews: dict[str, str] = {}
        for skill_name, variables in payloads.items():
            try:
                previews[skill_name] = render_skill_prompt(skill_name, variables, self.settings)[:600]
            except FileNotFoundError:
                continue
        previews["comparison"] = json.dumps(compare.model_dump(mode="json"), ensure_ascii=False)[:600]
        return previews

    def build_skill_outputs(
        self,
        branch_id: str,
        *,
        source_chapter_index: int,
        target_goal: str,
        draft: ChapterImitationDraft,
        strategy_input: dict[str, object] | None = None,
    ) -> dict[str, dict[str, object]]:
        plan = self.chapter_imitation.build_imitation_plan(
            branch_id,
            source_chapter_index=source_chapter_index,
            target_goal=target_goal,
        )
        planner_context = self.chapter_imitation.next_chapter_planner.build_context(
            branch_id,
            intent=ChapterPlanningIntent(
                primary_goal=target_goal,
                emphasis=["保持人物连续性", "保持冲突推进", "保持风格约束"],
                forbidden_moves=["不要无铺垫升级战力", "不要引入未准备的大设定"],
                preferred_tone="克制务实",
                pace="steady",
            ),
            window=PlannerContextWindow(recent_chapter_count=3),
        )
        title, source_text = self.chapter_imitation._source_chapter_text(branch_id, source_chapter_index)  # noqa: SLF001
        chapter_intake_output = {
            "chapter_index": source_chapter_index,
            "normalized_title": title,
            "cleaned_text": source_text[:2400],
            "paragraph_blocks": [
                {"order": idx, "text": block.strip()}
                for idx, block in enumerate([item for item in source_text.splitlines() if item.strip()][:6], start=1)
            ],
            "scene_candidates": [
                {"order": idx, "text": beat}
                for idx, beat in enumerate(plan.scene_beats[:4], start=1)
            ],
            "notes": [
                "已提取基础段落块供后续小模型处理。",
                "应关注章尾钩子与关系/规则敏感点。",
            ],
        }
        fact_output = {
            "characters": [{"label": item, "evidence": [item], "confidence": 0.6} for item in planner_context.active_characters[:3]],
            "events": [{"label": item, "evidence": [item], "confidence": 0.6} for item in planner_context.recent_chapter_summaries[:2]],
            "relations": [{"label": item, "evidence": [item], "confidence": 0.55} for item in planner_context.relationship_state_notes[:3]],
            "conflicts": [{"label": item, "evidence": [item], "confidence": 0.55} for item in planner_context.active_conflicts[:3]],
            "foreshadowing": [{"label": item, "evidence": [item], "confidence": 0.5} for item in planner_context.unresolved_threads[:3]],
            "worldbuilding_facts": [{"label": item, "evidence": [item], "confidence": 0.55} for item in planner_context.world_rules[:3]],
        }
        constraint_output = {
            "hard_constraints": plan.hard_constraints[:5],
            "soft_constraints": plan.soft_constraints[:5],
            "forbidden_transformations": [
                item
                for item in (planner_context.forbidden_moves[:3] + ["不要直接抄原文句式", "不要无铺垫升级战力"])
                if item
            ],
            "continuity_memory": (
                planner_context.relationship_state_notes[:2]
                + planner_context.unresolved_threads[:2]
                + planner_context.world_rules[:2]
            ),
            "relationship_watchpoints": planner_context.relationship_state_notes[:3],
            "rule_watchpoints": planner_context.world_rules[:3],
        }
        strategy = strategy_input or {}
        if strategy:
            prioritized_targets = [str(item) for item in strategy.get("prioritized_targets", []) if str(item).strip()]
            prioritized_families = [str(item) for item in strategy.get("prioritized_families", []) if str(item).strip()]
            if prioritized_targets:
                constraint_output["soft_constraints"] = constraint_output["soft_constraints"] + prioritized_targets[:2]
                constraint_output["continuity_memory"] = constraint_output["continuity_memory"] + prioritized_targets[:2]
            if prioritized_families:
                constraint_output["soft_constraints"] = constraint_output["soft_constraints"] + [f"family:{item}" for item in prioritized_families[:2]]
            blocking_issues = [str(item) for item in strategy.get("blocking_issues", []) if str(item).strip()]
            if blocking_issues:
                constraint_output["forbidden_transformations"] = constraint_output["forbidden_transformations"] + blocking_issues[:2]
        self_check_output = {
            "blocking_issues": [],
            "likely_gate_failures": [],
            "recommended_actions": [],
            "self_notes": [],
        }
        if len(draft.draft_text) < 180:
            self_check_output["blocking_issues"].append("draft_too_short_for_gate")
            self_check_output["recommended_actions"].append("补足中段阻力与章尾钩子。")
        if not constraint_output["forbidden_transformations"]:
            self_check_output["blocking_issues"].append("missing_forbidden_transformations")
            self_check_output["recommended_actions"].append("补齐换皮与越界禁止项。")
        if not constraint_output["relationship_watchpoints"]:
            self_check_output["likely_gate_failures"].append("relationship_transition_thin")
            self_check_output["recommended_actions"].append("补充关系变化敏感点。")
        if not constraint_output["rule_watchpoints"]:
            self_check_output["likely_gate_failures"].append("world_rule_support_thin")
            self_check_output["recommended_actions"].append("补充规则敏感点。")
        if "接下来" not in draft.draft_text and "下一步" not in draft.draft_text:
            self_check_output["likely_gate_failures"].append("ending_hook_presence")
            self_check_output["recommended_actions"].append("补充明确的下一步钩子。")
        if len(constraint_output["continuity_memory"]) < 2:
            self_check_output["likely_gate_failures"].append("continuity_memory_thin")
            self_check_output["recommended_actions"].append("补充关系/线程/规则 continuity memory。")
        if "决定" not in draft.draft_text and "选择" not in draft.draft_text:
            self_check_output["likely_gate_failures"].append("character_motivation_drift")
            self_check_output["recommended_actions"].append("补足人物动机与选择依据。")
        if plan.risk_focus:
            self_check_output["self_notes"].extend(plan.risk_focus[:2])
        if strategy:
            self_check_output["self_notes"].extend(
                [str(item) for item in strategy.get("recommended_actions", []) if str(item).strip()][:2]
            )
            self_check_output["self_notes"].extend(
                [f"family:{item}" for item in strategy.get("prioritized_families", []) if str(item).strip()][:2]
            )
        rhythm_output = {
            "pace_label": "steady" if len(plan.scene_beats) <= 4 else "dense",
            "hook_strength": 0.8 if ("接下来" in draft.draft_text or "下一步" in draft.draft_text) else 0.45,
            "tension_curve": ["setup", "resistance", "response", "hook"][: max(2, min(4, len(plan.scene_beats)))],
            "issues": [],
            "recommended_actions": [],
        }
        if len(plan.scene_beats) < 3:
            rhythm_output["issues"].append("scene_progression_thin")
            rhythm_output["recommended_actions"].append("补充至少一个中段阻力场景，拉开节奏层次。")
        if rhythm_output["hook_strength"] < 0.6:
            rhythm_output["issues"].append("hook_weak")
            rhythm_output["recommended_actions"].append("增强章尾钩子，提升读者续读驱动力。")
        if len(draft.draft_text) < 220:
            rhythm_output["issues"].append("pace_too_thin")
            rhythm_output["recommended_actions"].append("补足节奏起伏，不要只剩结果陈述。")
        reader_output = {
            "reader_profile": "core_web_novel_reader",
            "engagement_score": 78 if rhythm_output["hook_strength"] >= 0.6 else 61,
            "concerns": [],
            "recommended_actions": [],
        }
        if "决定" not in draft.draft_text and "选择" not in draft.draft_text:
            reader_output["concerns"].append("motivation_not_explicit")
            reader_output["recommended_actions"].append("让读者更清楚主角为何做出当前行动选择。")
        if "关系" not in "".join(plan.soft_constraints) and not planner_context.relationship_state_notes:
            reader_output["concerns"].append("relationship_signal_thin")
            reader_output["recommended_actions"].append("补一点人物互动或态度差异，让读者更容易跟住关系线。")
        if rhythm_output["hook_strength"] < 0.6:
            reader_output["concerns"].append("reader_hook_weak")
            reader_output["recommended_actions"].append("增强章尾期待感，避免读者觉得本章平收。")
        dialogue_output = {
            "issues": [],
            "speaker_hints": planner_context.active_characters[:3],
            "efficiency_notes": [],
            "recommended_actions": [],
        }
        if "“" not in draft.draft_text and '"' not in draft.draft_text:
            dialogue_output["issues"].append("dialogue_presence_thin")
            dialogue_output["recommended_actions"].append("补少量高信息密度对话，增强人物辨识度。")
        if not planner_context.relationship_state_notes:
            dialogue_output["issues"].append("speaker_relation_context_thin")
            dialogue_output["recommended_actions"].append("补说话人态度差异，避免对话无关系层次。")
        research_output = {
            "setting_notes": planner_context.world_rules[:3],
            "rule_reminders": planner_context.world_rules[:3],
            "audience_expectation_notes": [],
            "caution_points": [],
        }
        if not planner_context.world_rules:
            research_output["caution_points"].append("当前缺少明确世界规则提醒，易出现设定越界。")
        if "hook_weak" in rhythm_output["issues"]:
            research_output["audience_expectation_notes"].append("题材读者通常期待章尾有明确续读驱动力。")
        if strategy:
            prioritized_families = [str(item) for item in strategy.get("prioritized_families", []) if str(item).strip()]
            if "dialogue" in prioritized_families:
                dialogue_output["issues"].append("strategy_dialogue_focus")
                dialogue_output["recommended_actions"].append("本章优先补对话辨识度、对白信息效率和说话人区分。")
            if "research" in prioritized_families:
                research_output["caution_points"].append("本章被标记为 research 敏感，应优先核对设定、规则和题材预期。")
            if "reader" in prioritized_families:
                reader_output["concerns"].append("strategy_reader_focus")
                reader_output["recommended_actions"].append("本章优先补读者易卡点与续读期待。")
            if "rhythm" in prioritized_families:
                rhythm_output["issues"].append("strategy_rhythm_focus")
                rhythm_output["recommended_actions"].append("本章优先优化节奏起伏与章尾收束。")
        return {
            "chapter-intake": chapter_intake_output,
            "chapter-fact-extractor": fact_output,
            "imitation-constraint-pack": constraint_output,
            "draft-self-check": self_check_output,
            "rhythm-analyzer": rhythm_output,
            "reader-sim-review": reader_output,
            "dialogue-designer": dialogue_output,
            "research-pack": research_output,
        }

    def run_harness(
        self,
        branch_id: str,
        *,
        source_chapter_index: int,
        target_goal: str,
        max_rounds: int = 2,
        use_llm: bool = False,
        model_name: str | None = None,
        strategy_input: dict[str, object] | None = None,
    ) -> ChapterImitationHarnessReport:
        skill_contracts = self.list_skill_contracts()
        draft = (
            self.chapter_imitation.build_llm_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                target_goal=target_goal,
                model_name=model_name,
            )
            if use_llm
            else self.chapter_imitation.build_skeleton_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                target_goal=target_goal,
            )
        )

        rounds: list[ChapterImitationHarnessRound] = []
        stop_reason = "max_rounds_reached"
        final_preflight: ChapterImitationPreflightReport | None = None
        final_verdict = "needs_revision"
        final_actions: list[ChapterImitationHarnessAction] = []
        final_policy_summary: dict[str, object] = {}

        for round_index in range(1, max_rounds + 1):
            comparison = self.chapter_imitation.compare_with_source(
                branch_id,
                source_chapter_index=source_chapter_index,
                draft=draft,
            )
            skill_outputs = self.build_skill_outputs(
                branch_id,
                source_chapter_index=source_chapter_index,
                target_goal=target_goal,
                draft=draft,
                strategy_input=strategy_input,
            )
            preflight = self.preflight_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                draft=draft,
                comparison=comparison,
                skill_outputs=skill_outputs,
            )
            review = self.chapter_imitation.review_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                draft=draft,
            )
            gate = self.chapter_imitation.gate_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                draft=draft,
            )
            risk = self.chapter_imitation.risk_review_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                draft=draft,
            )
            skill_outputs["_gate_meta"] = {"overall_verdict": gate.overall_verdict, "needs_human_review": gate.needs_human_review}
            skill_outputs["_risk_meta"] = {"overall_risk_level": risk.overall_risk_level}
            preflight = self.preflight_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                draft=draft,
                comparison=comparison,
                skill_outputs=skill_outputs,
            )
            score = self.chapter_imitation.score_draft(
                source_chapter_index=source_chapter_index,
                draft=draft,
                comparison=comparison,
                gate=gate,
                risk=risk,
            )
            actions = self._sorted_actions(self._recommended_actions(preflight, review, gate, risk))
            revise_payload = self._build_revise_payload(
                actions=actions,
                preflight=preflight,
                gate=gate,
                risk=risk,
            )
            skill_prompt_previews = self.build_skill_prompt_previews(
                branch_id,
                source_chapter_index=source_chapter_index,
                target_goal=target_goal,
                draft=draft,
            )
            rounds.append(
                ChapterImitationHarnessRound(
                    round_index=round_index,
                    draft=draft,
                    comparison=comparison,
                    review=review,
                    gate=gate,
                    risk=risk,
                    score=score,
                    preflight=preflight,
                    actions=actions,
                    revise_payload=revise_payload,
                    skill_prompt_previews=skill_prompt_previews,
                    skill_outputs=skill_outputs,
                )
            )
            final_preflight = preflight

            final_verdict, stop_reason = self._aggregate_stop_reason(
                preflight=preflight,
                gate=gate,
                risk=risk,
                score=score,
                actions=actions,
            )
            final_actions = actions
            final_policy_summary = self._policy_summary(
                preflight=preflight,
                gate=gate,
                risk=risk,
                score=score,
                actions=actions,
                final_verdict=final_verdict,
                stop_reason=stop_reason,
            )
            if final_verdict == "pass":
                break

            draft = self._apply_actions_to_draft(
                draft,
                review=review,
                preflight=preflight,
                actions=actions,
                base_reviser=self.chapter_imitation.revise_draft,
            )

        assert final_preflight is not None
        return ChapterImitationHarnessReport(
            source_chapter_index=source_chapter_index,
            target_goal=target_goal,
            max_rounds=max_rounds,
            skill_contracts=skill_contracts,
            rounds=rounds,
            final_draft=draft,
            final_preflight=final_preflight,
            action_queue=final_actions,
            policy_summary=final_policy_summary,
            final_verdict=final_verdict,
            stop_reason=stop_reason,
        )

    @staticmethod
    def _recommended_actions(
        preflight: ChapterImitationPreflightReport,
        review: ChapterImitationReviewReport,
        gate: ChapterImitationGateReport,
        risk: ChapterImitationRiskReport,
    ) -> list[ChapterImitationHarnessAction]:
        actions: list[ChapterImitationHarnessAction] = []
        if "structure_alignment_failed" in preflight.blocking_issues:
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="replan",
                    target="source_skeleton",
                    severity="high",
                    priority=1,
                    instructions=["先修 scene beats 与原章结构对齐，再继续 prose 修订。"],
                )
            )
        if "draft_too_short_for_gate" in preflight.blocking_issues:
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="expand_middle",
                    target="draft_body",
                    severity="high",
                    priority=1,
                    instructions=["补足中段阻力、行动选择与章尾钩子承接。"],
                )
            )
        if "missing_forbidden_transformations" in preflight.blocking_issues:
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="repair_constraints",
                    target="constraint_pack",
                    severity="high",
                    priority=1,
                    instructions=["补齐 forbidden_transformations，避免换皮越界与原文复刻。"],
                )
            )
        if gate.needs_human_review:
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="quality_revision",
                    target="quality_gate",
                    severity="medium",
                    priority=2,
                    instructions=gate.quality_gate_notes[:2] or ["压缩 summary-like 表述，增强章节推进感。"],
                )
            )
        if risk.overall_risk_level != "low":
            severity, priority = HarnessControllerService._severity_priority("warn", risk_level=risk.overall_risk_level)
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="risk_revision",
                    target="risk_gate",
                    severity=severity,
                    priority=priority,
                    instructions=risk.top_risk_summaries[:2] or risk.coverage_gaps[:2],
                )
            )
        if (
            "continuity_memory_thin" in " ".join(preflight.recommended_actions)
            or any("continuity_memory" in issue for issue in preflight.blocking_issues)
        ):
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="repair_continuity_memory",
                    target="continuity_memory",
                    severity="medium",
                    priority=2,
                    instructions=["补充关系推进、未解线程与规则约束的 continuity memory。"],
                )
            )
        if "人物动机" in " ".join(preflight.recommended_actions):
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="repair_character_motivation",
                    target="character_motivation",
                    severity="medium",
                    priority=2,
                    instructions=["补足人物为何做出当前选择的支撑证据与过渡。"],
                )
            )
        if "关系变化" in " ".join(preflight.recommended_actions):
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="repair_relationship_transition",
                    target="relationship_transition",
                    severity="medium",
                    priority=2,
                    instructions=["补足关系变化前后的中间事件与态度转折。"],
                )
            )
        if "规则支撑" in " ".join(preflight.recommended_actions) or "规则敏感点" in " ".join(preflight.recommended_actions):
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="repair_world_rule_support",
                    target="world_rule_support",
                    severity="medium",
                    priority=2,
                    instructions=["补足越界动作前的规则来源、限制与代价。"],
                )
            )
        if "关系证据" in " ".join(preflight.recommended_actions):
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="repair_relation_evidence",
                    target="fact_relations",
                    severity="medium",
                    priority=3,
                    instructions=["补足人物互动、态度变化与关系状态证据。"],
                )
            )
        if "规则证据" in " ".join(preflight.recommended_actions):
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="repair_rule_evidence",
                    target="fact_rules",
                    severity="medium",
                    priority=3,
                    instructions=["补足世界规则、资源限制与动作代价证据。"],
                )
            )
        if "节奏" in " ".join(preflight.recommended_actions) or "钩子" in " ".join(preflight.recommended_actions):
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="repair_rhythm",
                    target="rhythm",
                    severity="medium",
                    priority=2,
                    instructions=["补足节奏起伏与章尾驱动力，避免章节推进过平。"],
                )
            )
        if "读者" in " ".join(preflight.recommended_actions) or "期待感" in " ".join(preflight.recommended_actions):
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="repair_reader_engagement",
                    target="reader_engagement",
                    severity="medium",
                    priority=3,
                    instructions=["补清读者易卡住的信息点，增强代入感与续读欲。"],
                )
            )
        if "对话" in " ".join(preflight.recommended_actions) or "说话人" in " ".join(preflight.recommended_actions):
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="repair_dialogue_design",
                    target="dialogue",
                    severity="medium",
                    priority=3,
                    instructions=["补充说话人区分与高信息密度对话。"],
                )
            )
        if "世界规则提醒" in " ".join(preflight.recommended_actions) or "题材读者" in " ".join(preflight.recommended_actions):
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="repair_research_alignment",
                    target="research_pack",
                    severity="medium",
                    priority=3,
                    instructions=["补 setting/rule/audience expectation 提示，避免设定和读者预期脱节。"],
                )
            )
        if "章尾钩子" in " ".join(preflight.recommended_actions):
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="reinforce_ending_hook",
                    target="ending_hook",
                    severity="medium",
                    priority=2,
                    instructions=["补出清晰的下一步驱动与未完成目标。"],
                )
            )
        if not actions:
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="polish",
                    target="draft",
                    severity="low",
                    priority=4,
                    instructions=review.revision_directions[:2],
                )
            )
        return actions
