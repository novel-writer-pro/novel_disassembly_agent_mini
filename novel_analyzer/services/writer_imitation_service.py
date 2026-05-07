"""Writer-facing imitation service — unified 拆书→仿写 pipeline.

Orchestrates the existing HarnessControllerService + ChapterImitationService
and produces writer-friendly reports, continuation notes, style fingerprints,
and cross-novel comparisons.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import (
    ChapterJob,
)
from novel_analyzer.domain.schemas import (
    ContinuationNotes,
    CrossNovelComparisonReport,
    WriterImitationReport,
    WriterStyleFingerprint,
)
from novel_analyzer.services.imitation_harness_service import HarnessControllerService


class WriterImitationService:
    """Writer-facing imitation workflow.

    Usage::

        service = WriterImitationService(session)
        report = service.imitate_chapter(
            branch_id,
            source_chapter_index=3,
            target_goal="延续主角获得功法后的克制成长",
        )
        # → WriterImitationReport with draft, risk review, continuation notes
    """

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self._harness = HarnessControllerService(session, self.settings)

    # ── primary entry: 拆书 → 仿写 → 风险控制 → 续写笔记 ─────────────────

    def imitate_chapter(
        self,
        branch_id: str,
        *,
        source_chapter_index: int,
        target_goal: str,
        max_rounds: int = 2,
        use_llm: bool = False,
        model_name: str | None = None,
    ) -> WriterImitationReport:
        """Run the full 拆书→仿写 pipeline and return a writer-friendly report.

        Steps:
        1. Deconstruct source chapter (via planner context)
        2. Build imitation constraint pack
        3. Generate draft (skeleton or LLM)
        4. Run all quality skills (rhythm, reader-sim, dialogue, style, research)
        5. Preflight + gate + risk review
        6. Extract continuation notes for next chapter
        """
        harness_report = self._harness.run_harness(
            branch_id,
            source_chapter_index=source_chapter_index,
            target_goal=target_goal,
            max_rounds=max_rounds,
            use_llm=use_llm,
            model_name=model_name,
        )

        final_round = harness_report.rounds[-1] if harness_report.rounds else None
        skill_outputs = final_round.skill_outputs if final_round else {}

        # ── extract quality signals from skill outputs ──
        rhythm = self._safe_dict(skill_outputs.get("rhythm-analyzer"))
        reader = self._safe_dict(skill_outputs.get("reader-sim-review"))
        dialogue = self._safe_dict(skill_outputs.get("dialogue-designer"))
        style = self._safe_dict(skill_outputs.get("style-calibrator"))

        # ── build continuation notes ──
        continuation = self._build_continuation_notes(
            branch_id=branch_id,
            source_chapter_index=source_chapter_index,
            harness_report=harness_report,
            skill_outputs=skill_outputs,
        )

        # ── assemble writer report ──
        source_title = harness_report.final_draft.original_title
        return WriterImitationReport(
            branch_id=branch_id,
            source_chapter_index=source_chapter_index,
            target_goal=target_goal,
            source_title=source_title,
            overall_score=harness_report.policy_summary.get("overall_score", 0),
            overall_risk_level=str(harness_report.policy_summary.get("risk_overall_level", "low")),
            final_verdict=harness_report.final_verdict,
            stop_reason=harness_report.stop_reason,
            draft_title=harness_report.final_draft.draft_title,
            draft_text=harness_report.final_draft.draft_text,
            rhythm=rhythm,
            reader_engagement=reader,
            dialogue_quality=dialogue,
            style_calibration=style,
            risk_level=str(harness_report.policy_summary.get("risk_overall_level", "low")),
            top_risks=[
                str(item)
                for item in harness_report.policy_summary.get("issue_families", [])[:5]
            ],
            coverage_gaps=[],
            blocking_issues=harness_report.final_preflight.blocking_issues,
            recommended_actions=harness_report.final_preflight.recommended_actions,
            revision_directions=harness_report.final_draft.method_notes[:5],
            writer_learning_notes=harness_report.final_draft.comparison_notes[:5],
            continuation_notes=continuation,
            harness_report=harness_report.model_dump(mode="json"),
        )

    # ── continuation notes ──────────────────────────────────────────────────

    def _build_continuation_notes(
        self,
        *,
        branch_id: str,
        source_chapter_index: int,
        harness_report,
        skill_outputs: dict[str, dict[str, object]],
    ) -> ContinuationNotes:
        """Extract structured carry-over notes for the next chapter."""
        constraint_pack = self._safe_dict(skill_outputs.get("imitation-constraint-pack"))

        # ── ending hook detection ──
        draft_text = harness_report.final_draft.draft_text
        ending_hook = ""
        for marker in ["下一步", "接下来", "将要", "必须", "需要尽快"]:
            idx = draft_text.rfind(marker)
            if idx > len(draft_text) // 2:
                snippet = draft_text[idx : idx + 80]
                ending_hook = snippet.replace("\n", " ").strip()
                break
        if not ending_hook:
            lines = [line.strip() for line in draft_text.splitlines() if line.strip()]
            ending_hook = lines[-1][:120] if lines else ""

        # ── active characters ──
        active_characters = [
            str(item).strip()
            for item in self._safe_list(constraint_pack.get("continuity_memory", []))[:6]
            if str(item).strip()
        ]

        # ── relationship state ──
        relationship_state = [
            str(item).strip()
            for item in self._safe_list(constraint_pack.get("relationship_watchpoints", []))[:4]
            if str(item).strip()
        ]

        # ── unresolved threads ──
        unresolved = [
            str(item).strip()
            for item in self._safe_list(constraint_pack.get("continuity_memory", []))[4:8]
            if str(item).strip()
        ]

        # ── world rules ──
        world_rules = [
            str(item).strip()
            for item in self._safe_list(constraint_pack.get("rule_watchpoints", []))[:4]
            if str(item).strip()
        ]

        # ── constraints ──
        hard = [
            str(item).strip()
            for item in self._safe_list(constraint_pack.get("hard_constraints", []))[:5]
            if str(item).strip()
        ]
        soft = [
            str(item).strip()
            for item in self._safe_list(constraint_pack.get("soft_constraints", []))[:5]
            if str(item).strip()
        ]
        forbidden = [
            str(item).strip()
            for item in self._safe_list(constraint_pack.get("forbidden_transformations", []))[:5]
            if str(item).strip()
        ]

        # ── risk watchpoints ──
        risk_focus = [
            str(item).strip()
            for item in harness_report.final_preflight.recommended_actions[:4]
            if str(item).strip()
        ]
        continuity_risks = [
            str(item).strip()
            for item in harness_report.final_preflight.blocking_issues[:4]
            if str(item).strip()
        ]

        # ── writer notes ──
        writer_notes = harness_report.final_draft.method_notes[:4]

        return ContinuationNotes(
            source_chapter_index=source_chapter_index,
            next_chapter_index=source_chapter_index + 1,
            chapter_summary=harness_report.final_draft.draft_text[:200],
            ending_hook=ending_hook,
            active_characters=active_characters,
            relationship_state=relationship_state,
            unresolved_threads=unresolved,
            world_rules=world_rules,
            hard_constraints=hard,
            soft_constraints=soft,
            forbidden_moves=forbidden,
            risk_focus=risk_focus,
            continuity_risks=continuity_risks,
            quality_reminders=harness_report.final_preflight.recommended_actions[:4],
            recommended_next_questions=[
                f"第{source_chapter_index + 1}章应该如何推进{goal}？"
                for goal in [harness_report.target_goal]
            ],
            writer_notes=writer_notes,
        )

    # ── multi-chapter imitation with carry-over ─────────────────────────────

    def imitate_chapter_range(
        self,
        branch_id: str,
        *,
        start_chapter: int,
        chapter_goals: list[tuple[int, str]],
        max_rounds: int = 2,
        use_llm: bool = False,
    ) -> list[WriterImitationReport]:
        """Run imitation across a range of chapters with carry-over of
        continuation notes between steps.

        Each step's continuation notes feed into the next step's strategy.
        """
        reports: list[WriterImitationReport] = []
        previous_continuation: ContinuationNotes | None = None

        for chapter_index, goal in chapter_goals:
            strategy_input: dict[str, object] = {}
            if previous_continuation is not None:
                strategy_input = {
                    "prioritized_targets": (
                        previous_continuation.relationship_state[:2]
                        + previous_continuation.unresolved_threads[:2]
                    ),
                    "prioritized_families": [
                        "continuity"
                    ],
                    "blocking_issues": previous_continuation.continuity_risks[:2],
                    "recommended_actions": previous_continuation.quality_reminders[:2],
                }

            # Use harness directly with strategy_input
            harness_report = self._harness.run_harness(
                branch_id,
                source_chapter_index=chapter_index,
                target_goal=goal,
                max_rounds=max_rounds,
                use_llm=use_llm,
                strategy_input=strategy_input if strategy_input else None,
            )

            report = self._harness_to_writer_report(
                branch_id, chapter_index, goal, harness_report
            )
            reports.append(report)
            previous_continuation = report.continuation_notes

        return reports

    # ── style fingerprint ───────────────────────────────────────────────────

    def build_style_fingerprint(
        self,
        branch_id: str,
        *,
        chapter_range: list[int] | None = None,
    ) -> WriterStyleFingerprint:
        """Build a style fingerprint from analyzed chapters.

        Aggregates style signals across the specified chapter range.
        """
        # Discover available chapters if range not specified
        if chapter_range is None:
            chapter_range = self._completed_chapter_indexes(branch_id)

        chapter_profiles: list[dict[str, object]] = []
        total_length = 0
        dialogue_lines = 0
        total_lines = 0

        for idx in chapter_range:
            try:
                title, text = self._harness.chapter_imitation._source_chapter_text(branch_id, idx)  # noqa: SLF001
            except ValueError:
                continue

            total_length += len(text)
            lines = text.splitlines()
            total_lines += len(lines)
            dialogue_lines += sum(1 for line in lines if "“" in line or '"' in line)

            chapter_profiles.append(
                {
                    "chapter_index": idx,
                    "title": title,
                    "length": len(text),
                    "paragraph_count": len([l for l in lines if l.strip()]),
                    "dialogue_ratio": (
                        round(
                            sum(1 for l in lines if "“" in l or '"' in l)
                            / max(1, len(lines)),
                            3,
                        )
                    ),
                }
            )

        chapter_count = len(chapter_profiles)
        avg_length = total_length / max(1, chapter_count)
        dialogue_ratio = dialogue_lines / max(1, total_lines)

        # Heuristic style classification
        if avg_length < 800:
            prose_density = "sparse"
        elif avg_length < 2000:
            prose_density = "balanced"
        else:
            prose_density = "dense"

        if dialogue_ratio > 0.35:
            narrative_distance = "close"
        elif dialogue_ratio > 0.15:
            narrative_distance = "mid"
        else:
            narrative_distance = "distant"

        style_axes = [
            f"文风密度: {prose_density}",
            f"叙事距离: {narrative_distance}",
            f"对话占比: {dialogue_ratio:.2f}",
            f"平均章节长度: {avg_length:.0f} 字符",
        ]

        pitfalls: list[str] = []
        if prose_density == "sparse":
            pitfalls.append("文风偏稀疏，仿写时易出现 prose_density_thin 风险。")
        if narrative_distance == "distant":
            pitfalls.append("叙事距离偏远，仿写时需注意读者代入感。")

        return WriterStyleFingerprint(
            branch_id=branch_id,
            chapter_range=chapter_range,
            prose_density=prose_density,
            avg_paragraph_length=avg_length / max(1, total_lines) if total_lines else 0,
            dialogue_ratio=dialogue_ratio,
            narrative_distance=narrative_distance,
            chapter_profiles=chapter_profiles,
            recommended_style_axes=style_axes,
            imitation_pitfalls=pitfalls,
        )

    # ── cross-novel comparison ──────────────────────────────────────────────

    def compare_novels(
        self,
        source_branch_id: str,
        reference_branch_id: str,
    ) -> CrossNovelComparisonReport:
        """Compare two novel branches across key writing dimensions."""
        source_chapters = self._completed_chapter_indexes(source_branch_id)
        ref_chapters = self._completed_chapter_indexes(reference_branch_id)

        # Gather chapter-level stats
        source_stats = self._chapter_stats(source_branch_id, source_chapters)
        ref_stats = self._chapter_stats(reference_branch_id, ref_chapters)

        key_differences: list[str] = []
        if source_stats["avg_length"] and ref_stats["avg_length"]:
            ratio = source_stats["avg_length"] / max(1, ref_stats["avg_length"])
            if ratio < 0.7:
                key_differences.append(
                    f"你的章节平均长度 ({source_stats['avg_length']:.0f}) 明显短于参考 ({ref_stats['avg_length']:.0f})"
                )
            elif ratio > 1.3:
                key_differences.append(
                    f"你的章节平均长度 ({source_stats['avg_length']:.0f}) 明显长于参考 ({ref_stats['avg_length']:.0f})"
                )

        if source_stats["dialogue_ratio"] and ref_stats["dialogue_ratio"]:
            dr = source_stats["dialogue_ratio"] / max(0.01, ref_stats["dialogue_ratio"])
            if dr < 0.6:
                key_differences.append("你的对话占比明显低于参考作品。")
            elif dr > 1.5:
                key_differences.append("你的对话占比明显高于参考作品。")

        recommendations: list[str] = []
        if key_differences:
            recommendations.append("对比差异点，检查是否符合你的写作意图。")
        recommendations.append("重点关注冲突密度和节奏起伏的差异，而非表面字数。")

        return CrossNovelComparisonReport(
            source_branch_id=source_branch_id,
            reference_branch_id=reference_branch_id,
            source_chapter_count=len(source_chapters),
            reference_chapter_count=len(ref_chapters),
            avg_chapter_length_source=int(source_stats["avg_length"]),
            avg_chapter_length_reference=int(ref_stats["avg_length"]),
            key_differences=key_differences,
            imitation_opportunities=[
                "从参考作品中学习钩子设计模式",
                "参考作品的冲突-应对-收束节奏",
            ],
            writer_recommendations=recommendations,
        )

    # ── helpers ─────────────────────────────────────────────────────────────

    def _harness_to_writer_report(
        self,
        branch_id: str,
        chapter_index: int,
        goal: str,
        harness_report,
    ) -> WriterImitationReport:
        """Convert a raw harness report to a writer-facing report."""
        final_round = harness_report.rounds[-1] if harness_report.rounds else None
        skill_outputs = final_round.skill_outputs if final_round else {}

        rhythm = self._safe_dict(skill_outputs.get("rhythm-analyzer"))
        reader = self._safe_dict(skill_outputs.get("reader-sim-review"))
        dialogue = self._safe_dict(skill_outputs.get("dialogue-designer"))
        style = self._safe_dict(skill_outputs.get("style-calibrator"))

        continuation = self._build_continuation_notes(
            branch_id=branch_id,
            source_chapter_index=chapter_index,
            harness_report=harness_report,
            skill_outputs=skill_outputs,
        )

        return WriterImitationReport(
            branch_id=branch_id,
            source_chapter_index=chapter_index,
            target_goal=goal,
            source_title=harness_report.final_draft.original_title,
            overall_score=harness_report.policy_summary.get("overall_score", 0),
            overall_risk_level=str(harness_report.policy_summary.get("risk_overall_level", "low")),
            final_verdict=harness_report.final_verdict,
            stop_reason=harness_report.stop_reason,
            draft_title=harness_report.final_draft.draft_title,
            draft_text=harness_report.final_draft.draft_text,
            rhythm=rhythm,
            reader_engagement=reader,
            dialogue_quality=dialogue,
            style_calibration=style,
            risk_level=str(harness_report.policy_summary.get("risk_overall_level", "low")),
            top_risks=[
                str(item)
                for item in harness_report.policy_summary.get("issue_families", [])[:5]
            ],
            blocking_issues=harness_report.final_preflight.blocking_issues,
            recommended_actions=harness_report.final_preflight.recommended_actions,
            revision_directions=harness_report.final_draft.method_notes[:5],
            writer_learning_notes=harness_report.final_draft.comparison_notes[:5],
            continuation_notes=continuation,
            harness_report=harness_report.model_dump(mode="json"),
        )

    def _completed_chapter_indexes(self, branch_id: str) -> list[int]:
        """Return sorted list of completed chapter indexes for a branch."""
        jobs = (
            self.session.execute(
                select(ChapterJob.chapter_index)
                .where(ChapterJob.branch_id == branch_id)
                .where(ChapterJob.status == "succeeded")
                .order_by(ChapterJob.chapter_index)
            )
            .scalars()
            .all()
        )
        return list(jobs)

    def _chapter_stats(
        self, branch_id: str, chapter_indexes: list[int]
    ) -> dict[str, float]:
        """Compute aggregated chapter statistics."""
        if not chapter_indexes:
            return {"avg_length": 0.0, "dialogue_ratio": 0.0}

        total_length = 0
        total_dialogue = 0
        total_lines = 0

        for idx in chapter_indexes:
            try:
                _title, text = self._harness.chapter_imitation._source_chapter_text(branch_id, idx)  # noqa: SLF001
            except ValueError:
                continue
            total_length += len(text)
            lines = text.splitlines()
            total_lines += len(lines)
            total_dialogue += sum(1 for line in lines if "“" in line or '"' in line)

        count = max(1, len(chapter_indexes))
        return {
            "avg_length": total_length / count,
            "dialogue_ratio": total_dialogue / max(1, total_lines),
        }

    @staticmethod
    def _safe_dict(value: object) -> dict[str, object]:
        """Coerce value to a string-keyed dict, returning empty dict on failure."""
        if isinstance(value, dict):
            return {str(k): v for k, v in value.items()}  # type: ignore[union-attr]
        return {}

    @staticmethod
    def _safe_list(value: object) -> list[object]:
        """Coerce value to a list, returning empty list on failure."""
        if isinstance(value, list):
            return value
        return []
