"""Controlled imitation harness with skill contracts and deterministic preflight checks."""

from __future__ import annotations

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
)
from novel_analyzer.services.chapter_imitation_service import ChapterImitationService


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

    def list_skill_contracts(self) -> list[ChapterImitationSkillContract]:
        root = Path(self.settings.skills_dir)
        contracts: list[ChapterImitationSkillContract] = []
        for skill_name, purpose, required_inputs, produced_outputs in self.IMITATION_SKILLS:
            prompt_asset = root / skill_name / "prompts" / "main.md"
            schema_asset = root / skill_name / "schemas" / "output.schema.json"
            contracts.append(
                ChapterImitationSkillContract(
                    skill_name=skill_name,
                    purpose=purpose,
                    required_inputs=required_inputs,
                    produced_outputs=produced_outputs,
                    prompt_asset_path=str(prompt_asset),
                    schema_asset_path=str(schema_asset),
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
    ) -> ChapterImitationPreflightReport:
        compare = comparison or self.chapter_imitation.compare_with_source(
            branch_id,
            source_chapter_index=source_chapter_index,
            draft=draft,
        )
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
                    notes=[f"draft/source 长度比过低：{length_ratio:.2f}"],
                )
            )
        else:
            checks.append(
                ChapterImitationPreflightCheck(
                    check_name="length_ratio",
                    status="pass",
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
                    notes=["comparison.overall_verdict != aligned"],
                )
            )
        else:
            checks.append(
                ChapterImitationPreflightCheck(
                    check_name="structure_alignment",
                    status="pass",
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
                    notes=["检测到疑似直接抄原文信号。"],
                )
            )
        else:
            checks.append(
                ChapterImitationPreflightCheck(
                    check_name="direct_copy_guard",
                    status="pass",
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
                    notes=["未检测到显式下一步钩子词。"],
                )
            )
        else:
            checks.append(
                ChapterImitationPreflightCheck(
                    check_name="ending_hook_presence",
                    status="pass",
                    notes=["检测到下一步/钩子相关收束。"],
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

    def run_harness(
        self,
        branch_id: str,
        *,
        source_chapter_index: int,
        target_goal: str,
        max_rounds: int = 2,
        use_llm: bool = False,
        model_name: str | None = None,
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

        for round_index in range(1, max_rounds + 1):
            comparison = self.chapter_imitation.compare_with_source(
                branch_id,
                source_chapter_index=source_chapter_index,
                draft=draft,
            )
            preflight = self.preflight_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                draft=draft,
                comparison=comparison,
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
            score = self.chapter_imitation.score_draft(
                source_chapter_index=source_chapter_index,
                draft=draft,
                comparison=comparison,
                gate=gate,
                risk=risk,
            )
            actions = self._recommended_actions(preflight, review, gate, risk)
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
                )
            )
            final_preflight = preflight

            if (
                preflight.overall_verdict == "pass"
                and comparison.overall_verdict == "aligned"
                and gate.overall_verdict != "needs_revision"
                and risk.overall_risk_level == "low"
                and score.overall_score >= 80
            ):
                stop_reason = "harness_quality_threshold_reached"
                final_verdict = "pass"
                break

            revised = self.chapter_imitation.revise_draft(draft, review=review)
            draft = revised.model_copy(
                update={
                    "risk_gate_notes": revised.risk_gate_notes + preflight.recommended_actions[:2],
                    "method_notes": revised.method_notes + [item.target for item in actions],
                }
            )
            final_verdict = "needs_revision"

        assert final_preflight is not None
        return ChapterImitationHarnessReport(
            source_chapter_index=source_chapter_index,
            target_goal=target_goal,
            max_rounds=max_rounds,
            skill_contracts=skill_contracts,
            rounds=rounds,
            final_draft=draft,
            final_preflight=final_preflight,
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
                    instructions=["先修 scene beats 与原章结构对齐，再继续 prose 修订。"],
                )
            )
        if "draft_too_short_for_gate" in preflight.blocking_issues:
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="expand_middle",
                    target="draft_body",
                    instructions=["补足中段阻力、行动选择与章尾钩子承接。"],
                )
            )
        if gate.needs_human_review:
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="quality_revision",
                    target="quality_gate",
                    instructions=gate.quality_gate_notes[:2] or ["压缩 summary-like 表述，增强章节推进感。"],
                )
            )
        if risk.overall_risk_level != "low":
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="risk_revision",
                    target="risk_gate",
                    instructions=risk.top_risk_summaries[:2] or risk.coverage_gaps[:2],
                )
            )
        if not actions:
            actions.append(
                ChapterImitationHarnessAction(
                    action_type="polish",
                    target="draft",
                    instructions=review.revision_directions[:2],
                )
            )
        return actions
