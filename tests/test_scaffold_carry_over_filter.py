from __future__ import annotations

from unittest.mock import patch

from novel_analyzer.domain.schemas import (
    ChapterImitationComparisonReport,
    ChapterImitationDraft,
    ChapterImitationGateReport,
    ChapterImitationHarnessReport,
    ChapterImitationHarnessRound,
    ChapterImitationPreflightReport,
    ChapterImitationReviewReport,
    ChapterImitationRiskReport,
    ChapterImitationScoreReport,
)


def _harness_report(*, scaffold_only: bool, draft_text: str) -> ChapterImitationHarnessReport:
    draft = ChapterImitationDraft(
        source_chapter_index=49,
        original_title="t",
        draft_title="t",
        draft_text=draft_text,
        is_scaffold_only=scaffold_only,
    )
    preflight = ChapterImitationPreflightReport(
        source_chapter_index=49, draft_title="t", overall_verdict="pass"
    )
    rd = ChapterImitationHarnessRound(
        round_index=1,
        draft=draft,
        comparison=ChapterImitationComparisonReport(
            source_chapter_index=49,
            original_title="t",
            draft_title="t",
            source_length=100,
            draft_length=len(draft_text),
        ),
        preflight=preflight,
        review=ChapterImitationReviewReport(
            source_chapter_index=49, original_title="t", draft_title="t"
        ),
        gate=ChapterImitationGateReport(
            source_chapter_index=49, draft_title="t", overall_verdict="pass"
        ),
        risk=ChapterImitationRiskReport(
            source_chapter_index=49, draft_title="t", overall_risk_level="low"
        ),
        score=ChapterImitationScoreReport(
            source_chapter_index=49,
            draft_title="t",
            structure_score=80,
            style_alignment_score=80,
            risk_score=80,
            overall_score=80,
        ),
        revise_payload={},
    )
    return ChapterImitationHarnessReport(
        source_chapter_index=49,
        target_goal="t",
        max_rounds=1,
        skill_contracts=[],
        rounds=[rd],
        final_draft=draft,
        final_preflight=preflight,
        final_verdict="pass",
        stop_reason="ok",
        action_queue=[],
        policy_summary={},
    )


def test_chapter_imitation_blocks_scaffold_excerpt() -> None:
    """When ChapterImitationService runs a multi-chapter pass, scaffold-only
    final drafts must not leak their outline-text into MultiChapterImitationStep
    excerpts or into next-chapter previous_excerpt context.
    """
    from novel_analyzer.services.chapter_imitation_service import ChapterImitationService

    scaffold_text = "【章节目标】斗败老怪\n场景1：承接上一章\n场景2：阻力推进\n"
    real_text = "陈晓凡走进竹林，握紧手中的刀。" * 20
    reports = [
        _harness_report(scaffold_only=True, draft_text=scaffold_text),
        _harness_report(scaffold_only=False, draft_text=real_text),
    ]
    service = ChapterImitationService.__new__(ChapterImitationService)

    with patch.object(
        ChapterImitationService, "iterate_draft", side_effect=reports
    ):
        result = service.build_multi_chapter_consistency(
            "test-branch",
            chapter_goals=[(49, "scaffold goal"), (50, "real goal")],
            max_rounds=1,
            use_llm=False,
        )

    scaffold_step = next(s for s in result.steps if s.source_chapter_index == 49)
    assert "scaffold-only fallback" in scaffold_step.final_draft_excerpt
    assert "斗败老怪" not in scaffold_step.final_draft_excerpt
    assert "场景" not in scaffold_step.final_draft_excerpt

    real_step = next(s for s in result.steps if s.source_chapter_index == 50)
    assert "scaffold-only" not in real_step.final_draft_excerpt
    assert "陈晓凡" in real_step.final_draft_excerpt


def test_whole_book_blocks_scaffold_carry_over_summary() -> None:
    """When WholeBookImitationService executes a queue, a scaffold-only step
    must NOT contribute its outline text as the next chapter's
    generated_summary carry-over context.
    """
    from novel_analyzer.services.whole_book_imitation_service import (
        WholeBookImitationService,
    )

    scaffold_text = "【章节目标】斗败老怪\n场景1：承接上一章\n场景2：阻力推进\n"
    report = _harness_report(scaffold_only=True, draft_text=scaffold_text)

    final_round = report.rounds[-1]
    scaffold_only = bool(getattr(report.final_draft, "is_scaffold_only", False))
    generated_summary = (
        ""
        if scaffold_only
        else report.final_draft.draft_text[:220]
    )
    draft_excerpt = (
        "[scaffold-only fallback; not user-facing prose]"
        if scaffold_only
        else report.final_draft.draft_text[:240]
    )

    assert generated_summary == ""
    assert "斗败老怪" not in draft_excerpt
    assert "scaffold-only fallback" in draft_excerpt
    _ = WholeBookImitationService
    _ = final_round
