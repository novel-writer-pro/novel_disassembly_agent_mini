from pathlib import Path

from langchain_core.messages import AIMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novel_analyzer.database.models import (
    AnalysisRun,
    ChapterArtifact,
    ChapterManifest,
    ChapterSegment,
    FactRecord,
    NovelSource,
    RunBranch,
)
from novel_analyzer.database.session import create_schema
from novel_analyzer.services.imitation_harness_service import HarnessControllerService


def _seed_branch(session, source_path: Path) -> str:
    text = (
        "第1章 大器晚成\n"
        "卫图觉醒命格并决定寻找养生功。\n"
        "第2章 二姑卫荭\n"
        "卫图拜访二姑，为资源铺垫。\n"
        "第3章 养生功法\n"
        "卫图求得龟息养气功并开始修炼。\n"
    )
    source_path.write_text(text, encoding="utf-8")

    novel = NovelSource(
        id="novel-harness-1",
        title="示例小说",
        source_path=str(source_path),
        source_hash="hash",
        metadata_json={},
    )
    manifest = ChapterManifest(
        id="manifest-harness-1",
        novel_id=novel.id,
        version=1,
        splitter_version="heuristic-v1",
        chapter_count=3,
        notes={},
    )
    run = AnalysisRun(
        id="run-harness-1",
        novel_id=novel.id,
        manifest_id=manifest.id,
        llm_base_url="https://example.invalid/v1",
        llm_model_name="gpt-5.4-mini",
        analysis_profile={},
        active_branch_id="branch-harness-1",
    )
    branch = RunBranch(
        id="branch-harness-1",
        run_id=run.id,
        name="main",
        parent_branch_id=None,
        fork_after_chapter_index=0,
        status="active",
    )
    session.add_all([novel, manifest, run, branch])
    session.flush()
    session.add_all(
        [
            ChapterSegment(
                manifest_id=manifest.id,
                chapter_index=1,
                raw_heading="第1章 大器晚成",
                normalized_chapter_no=1,
                normalized_title="大器晚成",
                start_offset=0,
                end_offset=text.index("第2章"),
                content_hash="c1",
            ),
            ChapterSegment(
                manifest_id=manifest.id,
                chapter_index=2,
                raw_heading="第2章 二姑卫荭",
                normalized_chapter_no=2,
                normalized_title="二姑卫荭",
                start_offset=text.index("第2章"),
                end_offset=text.index("第3章"),
                content_hash="c2",
            ),
            ChapterSegment(
                manifest_id=manifest.id,
                chapter_index=3,
                raw_heading="第3章 养生功法",
                normalized_chapter_no=3,
                normalized_title="养生功法",
                start_offset=text.index("第3章"),
                end_offset=len(text),
                content_hash="c3",
            ),
            ChapterArtifact(
                branch_id=branch.id,
                chapter_index=1,
                artifact_type="chapter_analysis",
                payload_json={
                    "chapter_summary": "卫图觉醒命格并决定寻找养生功。",
                    "continuity_notes": ["开篇建立命格与求生主线。"],
                },
                status="validated",
                visibility="active",
                source_kind="analysis",
                participates_in_downstream=True,
                inherited_from_branch_id=None,
                is_inherited=False,
            ),
            ChapterArtifact(
                branch_id=branch.id,
                chapter_index=2,
                artifact_type="chapter_analysis",
                payload_json={
                    "chapter_summary": "卫图拜访二姑，为资源铺垫。",
                    "continuity_notes": ["求助受阻，关系推进要有中间证据。"],
                },
                status="validated",
                visibility="active",
                source_kind="analysis",
                participates_in_downstream=True,
                inherited_from_branch_id=None,
                is_inherited=False,
            ),
            FactRecord(
                branch_id=branch.id,
                chapter_index=1,
                fact_type="entity",
                label="卫图",
                evidence_list=["卫图觉醒命格"],
                confidence=0.9,
            ),
        ]
    )
    session.commit()
    return branch.id


def test_harness_lists_skill_contracts(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        _seed_branch(session, tmp_path / "sample.txt")
        service = HarnessControllerService(session)
        contracts = service.list_skill_contracts()
        names = {item.skill_name for item in contracts}
        assert "chapter-intake" in names
        assert "imitation-constraint-pack" in names
        assert "draft-self-check" in names
        assert any(item.prompt_preview for item in contracts if item.skill_name == "chapter-intake")


def test_harness_preflight_blocks_too_short_draft(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        service = HarnessControllerService(session)
        draft = service.chapter_imitation.build_skeleton_draft(
            branch_id,
            source_chapter_index=3,
            target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
        )
        short_draft = draft.model_copy(update={"draft_text": "太短了"})
        comparison = service.chapter_imitation.compare_with_source(
            branch_id,
            source_chapter_index=3,
            draft=short_draft,
        )
        report = service.preflight_draft(
            branch_id,
            source_chapter_index=3,
            draft=short_draft,
            comparison=comparison,
            skill_outputs={
                "draft-self-check": {
                    "blocking_issues": ["draft_too_short_for_gate"],
                    "recommended_actions": ["补足中段阻力与章尾钩子。"],
                }
            },
        )
        assert report.overall_verdict == "block"
        assert "draft_too_short_for_gate" in report.blocking_issues
        assert any(item.severity == "high" and item.priority == 1 for item in report.checks)


def test_harness_run_returns_rounds(monkeypatch, tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        service = HarnessControllerService(session)

        class _DummyModel:
            def invoke(self, _prompt: str):
                return AIMessage(
                    content="""
{
  "draft_title": "养生功法",
  "draft_text": "卫图保持克制，梳理所得功法与下一步安排，决定继续推进修炼与资源筹措，接下来还要应对身份限制与新的阻力。",
  "method_notes": ["保持原章克制推进节奏"],
  "comparison_notes": ["仍保留受挫后转修炼的骨架"],
  "risk_gate_notes": ["重点检查 OOC 与剧情推进支撑缺口"]
}
""".strip()
                )

        monkeypatch.setattr(
            "novel_analyzer.services.chapter_imitation_service.build_chat_model",
            lambda *args, **kwargs: _DummyModel(),
        )

        report = service.run_harness(
            branch_id,
            source_chapter_index=3,
            target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
            max_rounds=1,
            use_llm=True,
        )
        assert report.skill_contracts
        assert report.rounds
        assert report.final_preflight
        assert report.rounds[0].skill_prompt_previews
        assert "draft-self-check" in report.rounds[0].skill_prompt_previews
        assert any(contract.skill_name == "style-calibrator" for contract in report.skill_contracts)
        assert report.rounds[0].skill_outputs
        assert "chapter-intake" in report.rounds[0].skill_outputs
        assert "chapter-fact-extractor" in report.rounds[0].skill_outputs
        assert "imitation-constraint-pack" in report.rounds[0].skill_outputs
        assert "relationship_watchpoints" in report.rounds[0].skill_outputs["imitation-constraint-pack"]
        assert "likely_gate_failures" in report.rounds[0].skill_outputs["draft-self-check"]
        assert report.rounds[0].revise_payload
        assert report.action_queue
        assert report.policy_summary
        assert "highest_action_priority" in report.policy_summary
        assert "weak_lane_action_count" in report.policy_summary
        if report.final_verdict != "pass":
            assert any("ACTION:" in item for item in report.final_draft.comparison_notes)
            assert "【Harness Action Queue】" not in report.final_draft.draft_text
            assert report.final_draft.action_queue
            assert all(
                hasattr(item, "action_type") and hasattr(item, "priority")
                for item in report.final_draft.action_queue
            )


def test_harness_strategy_input_influences_constraint_outputs(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        service = HarnessControllerService(session)
        draft = service.chapter_imitation.build_skeleton_draft(
            branch_id,
            source_chapter_index=3,
            target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
        )
        outputs = service.build_skill_outputs(
            branch_id,
            source_chapter_index=3,
            target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
            draft=draft,
            strategy_input={
                "prioritized_targets": ["relationship_transition", "world_rule_support"],
                "prioritized_families": ["relationship", "rule", "style", "dialogue", "reader_sim", "research"],
                "blocking_issues": ["gate_verdict_requires_revision"],
                "recommended_actions": ["补足关系与规则说明。"],
            },
        )
        constraint_output = outputs["imitation-constraint-pack"]
        self_check_output = outputs["draft-self-check"]
        style_output = outputs["style-calibrator"]
        rhythm_output = outputs["rhythm-analyzer"]
        reader_output = outputs["reader-sim-review"]
        dialogue_output = outputs["dialogue-designer"]
        research_output = outputs["research-pack"]
        assert "relationship_transition" in constraint_output["soft_constraints"]
        assert "family:relationship" in constraint_output["soft_constraints"]
        assert "gate_verdict_requires_revision" in constraint_output["forbidden_transformations"]
        assert "补足关系与规则说明。" in self_check_output["self_notes"]
        assert "family:relationship" in self_check_output["self_notes"]
        assert "prose_density_label" in style_output
        assert "style_axes" in style_output
        assert "hook_strength" in rhythm_output
        assert "engagement_score" in reader_output
        assert "strategy_style_focus" in style_output["style_issues"]
        assert "strategy_dialogue_focus" in dialogue_output["issues"]
        assert "strategy_reader_focus" in reader_output["concerns"]
        assert any("research 敏感" in item for item in research_output["caution_points"])


def test_harness_steering_pack_flows_into_constraint_outputs(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        service = HarnessControllerService(session)
        draft = service.chapter_imitation.build_skeleton_draft(
            branch_id,
            source_chapter_index=3,
            target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
            steering_pack={"worldview_capsule": ["宗门税制化"], "trope_axes": ["账本修仙"]},
        )
        outputs = service.build_skill_outputs(
            branch_id,
            source_chapter_index=3,
            target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
            draft=draft,
            steering_pack={
                "worldview_capsule": ["宗门税制化"],
                "trope_axes": ["账本修仙"],
                "innovation_directives": ["把功法收益折算成地位博弈"],
                "external_knowledge_refs": ["读者期待阶层跃迁的可见账本"],
            },
        )
        constraint_output = outputs["imitation-constraint-pack"]
        assert "宗门税制化" in constraint_output["worldview_capsule"]
        assert "账本修仙" in constraint_output["trope_axes"]
        assert any("trope:" in item for item in constraint_output["continuity_memory"])


def test_harness_actions_include_constraint_and_memory_repairs(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        service = HarnessControllerService(session)
        actions = service._recommended_actions(  # noqa: SLF001
            preflight=service.preflight_draft(
                branch_id,
                source_chapter_index=3,
                draft=service.chapter_imitation.build_skeleton_draft(
                    branch_id,
                    source_chapter_index=3,
                    target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
                ).model_copy(update={"draft_text": "接下来"}),
                skill_outputs={
                    "imitation-constraint-pack": {
                        "hard_constraints": [],
                        "soft_constraints": [],
                        "forbidden_transformations": [],
                        "continuity_memory": [],
                    },
                    "draft-self-check": {
                        "blocking_issues": ["missing_forbidden_transformations", "continuity_memory_thin"],
                        "recommended_actions": ["补充 continuity memory。"],
                    },
                },
            ),
            review=service.chapter_imitation.review_draft(
                branch_id,
                source_chapter_index=3,
                draft=service.chapter_imitation.build_skeleton_draft(
                    branch_id,
                    source_chapter_index=3,
                    target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
                ),
            ),
            gate=service.chapter_imitation.gate_draft(
                branch_id,
                source_chapter_index=3,
                draft=service.chapter_imitation.build_skeleton_draft(
                    branch_id,
                    source_chapter_index=3,
                    target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
                ),
            ),
            risk=service.chapter_imitation.risk_review_draft(
                branch_id,
                source_chapter_index=3,
                draft=service.chapter_imitation.build_skeleton_draft(
                    branch_id,
                    source_chapter_index=3,
                    target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
                ),
            ),
        )
        action_types = {item.action_type for item in actions}
        assert "repair_constraints" in action_types
        assert "repair_continuity_memory" in action_types


def test_harness_actions_include_relationship_rule_and_hook_repairs(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        service = HarnessControllerService(session)
        draft = service.chapter_imitation.build_skeleton_draft(
            branch_id,
            source_chapter_index=3,
            target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
        ).model_copy(update={"draft_text": "短草案"})
        preflight = service.preflight_draft(
            branch_id,
            source_chapter_index=3,
            draft=draft,
            skill_outputs={
                "imitation-constraint-pack": {
                    "hard_constraints": [],
                    "soft_constraints": [],
                    "forbidden_transformations": ["不要直接抄原文句式"],
                    "continuity_memory": [],
                    "relationship_watchpoints": [],
                    "rule_watchpoints": [],
                },
                "draft-self-check": {
                    "blocking_issues": [],
                    "likely_gate_failures": [
                        "relationship_transition_thin",
                        "world_rule_support_thin",
                        "ending_hook_presence",
                        "character_motivation_drift",
                    ],
                    "recommended_actions": [],
                },
            },
        )
        actions = service._recommended_actions(  # noqa: SLF001
            preflight=preflight,
            review=service.chapter_imitation.review_draft(
                branch_id,
                source_chapter_index=3,
                draft=service.chapter_imitation.build_skeleton_draft(
                    branch_id,
                    source_chapter_index=3,
                    target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
                ),
            ),
            gate=service.chapter_imitation.gate_draft(
                branch_id,
                source_chapter_index=3,
                draft=service.chapter_imitation.build_skeleton_draft(
                    branch_id,
                    source_chapter_index=3,
                    target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
                ),
            ),
            risk=service.chapter_imitation.risk_review_draft(
                branch_id,
                source_chapter_index=3,
                draft=service.chapter_imitation.build_skeleton_draft(
                    branch_id,
                    source_chapter_index=3,
                    target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
                ),
            ),
        )
        action_types = {item.action_type for item in actions}
        assert "repair_character_motivation" in action_types
        assert "repair_relationship_transition" in action_types
        assert "repair_world_rule_support" in action_types
        assert "reinforce_ending_hook" in action_types
        assert any(item.priority <= 2 for item in actions)


def test_harness_actions_include_rhythm_and_reader_repairs(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        service = HarnessControllerService(session)
        draft = service.chapter_imitation.build_skeleton_draft(
            branch_id,
            source_chapter_index=3,
            target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
        )
        preflight = service.preflight_draft(
            branch_id,
            source_chapter_index=3,
            draft=draft,
            skill_outputs={
                "rhythm-analyzer": {
                    "issues": ["hook_weak", "pace_too_thin"],
                    "recommended_actions": ["补足节奏起伏。", "增强读者期待感。"],
                    "hook_strength": 0.4,
                },
                "reader-sim-review": {
                    "concerns": ["reader_hook_weak"],
                    "recommended_actions": ["增强读者期待感。"],
                    "engagement_score": 58,
                },
            },
        )
        actions = service._recommended_actions(  # noqa: SLF001
            preflight=preflight,
            review=service.chapter_imitation.review_draft(
                branch_id,
                source_chapter_index=3,
                draft=draft,
            ),
            gate=service.chapter_imitation.gate_draft(
                branch_id,
                source_chapter_index=3,
                draft=draft,
            ),
            risk=service.chapter_imitation.risk_review_draft(
                branch_id,
                source_chapter_index=3,
                draft=draft,
            ),
        )
        action_types = {item.action_type for item in actions}
        assert "repair_rhythm" in action_types
        assert "repair_reader_engagement" in action_types


def test_harness_actions_include_dialogue_and_research_repairs(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        service = HarnessControllerService(session)
        draft = service.chapter_imitation.build_skeleton_draft(
            branch_id,
            source_chapter_index=3,
            target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
        )
        preflight = service.preflight_draft(
            branch_id,
            source_chapter_index=3,
            draft=draft,
            skill_outputs={
                "dialogue-designer": {
                    "issues": ["dialogue_presence_thin"],
                    "speaker_hints": [],
                    "efficiency_notes": [],
                    "recommended_actions": ["补一点人物对话，增强辨识度。"],
                },
                "research-pack": {
                    "setting_notes": [],
                    "rule_reminders": [],
                    "audience_expectation_notes": ["题材读者期待更明确钩子。"],
                    "caution_points": ["世界规则提醒不足。"],
                },
            },
        )
        actions = service._recommended_actions(  # noqa: SLF001
            preflight=preflight,
            review=service.chapter_imitation.review_draft(
                branch_id,
                source_chapter_index=3,
                draft=draft,
            ),
            gate=service.chapter_imitation.gate_draft(
                branch_id,
                source_chapter_index=3,
                draft=draft,
            ),
            risk=service.chapter_imitation.risk_review_draft(
                branch_id,
                source_chapter_index=3,
                draft=draft,
            ),
        )
        action_types = {item.action_type for item in actions}
        assert "repair_dialogue_design" in action_types
        assert "repair_research_alignment" in action_types
        assert any(item.priority <= 3 for item in actions if item.action_type in {"repair_dialogue_design", "repair_research_alignment"})


def test_harness_actions_include_relation_and_rule_evidence_repairs(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        service = HarnessControllerService(session)
        draft = service.chapter_imitation.build_skeleton_draft(
            branch_id,
            source_chapter_index=3,
            target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
        )
        preflight = service.preflight_draft(
            branch_id,
            source_chapter_index=3,
            draft=draft,
            skill_outputs={
                "chapter-intake": {"notes": ["章尾应保持推进感。"]},
                "chapter-fact-extractor": {
                    "characters": [],
                    "events": [],
                    "relations": [],
                    "conflicts": [],
                    "foreshadowing": [],
                    "worldbuilding_facts": [],
                },
                "imitation-constraint-pack": {
                    "hard_constraints": [],
                    "soft_constraints": [],
                    "forbidden_transformations": ["不要直接抄原文句式"],
                    "continuity_memory": ["旧线索"],
                    "relationship_watchpoints": ["卫图与二姑关系变化"],
                    "rule_watchpoints": ["功法资源限制"],
                },
                "draft-self-check": {
                    "blocking_issues": [],
                    "likely_gate_failures": [],
                    "recommended_actions": [],
                },
            },
        )
        actions = service._recommended_actions(  # noqa: SLF001
            preflight=preflight,
            review=service.chapter_imitation.review_draft(
                branch_id,
                source_chapter_index=3,
                draft=draft,
            ),
            gate=service.chapter_imitation.gate_draft(
                branch_id,
                source_chapter_index=3,
                draft=draft,
            ),
            risk=service.chapter_imitation.risk_review_draft(
                branch_id,
                source_chapter_index=3,
                draft=draft,
            ),
        )
        action_types = {item.action_type for item in actions}
        assert "repair_relation_evidence" in action_types
        assert "repair_rule_evidence" in action_types


def test_harness_preflight_consumes_gate_and_risk_meta(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        service = HarnessControllerService(session)
        draft = service.chapter_imitation.build_skeleton_draft(
            branch_id,
            source_chapter_index=3,
            target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
        )
        report = service.preflight_draft(
            branch_id,
            source_chapter_index=3,
            draft=draft,
            skill_outputs={
                "_gate_meta": {"overall_verdict": "needs_revision"},
                "_risk_meta": {"overall_risk_level": "medium"},
            },
        )
        assert "gate_verdict_requires_revision" in report.blocking_issues
        assert any(item.check_name == "risk_gate_alignment" for item in report.checks)


def test_harness_actions_are_sorted_by_priority_and_stop_reason_aggregates(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        service = HarnessControllerService(session)
        draft = service.chapter_imitation.build_skeleton_draft(
            branch_id,
            source_chapter_index=3,
            target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
        ).model_copy(update={"draft_text": "短草案"})
        comparison = service.chapter_imitation.compare_with_source(
            branch_id,
            source_chapter_index=3,
            draft=draft,
        )
        gate = service.chapter_imitation.gate_draft(
            branch_id,
            source_chapter_index=3,
            draft=draft,
        )
        risk = service.chapter_imitation.risk_review_draft(
            branch_id,
            source_chapter_index=3,
            draft=draft,
        )
        score = service.chapter_imitation.score_draft(
            source_chapter_index=3,
            draft=draft,
            comparison=comparison,
            gate=gate,
            risk=risk,
        )
        preflight = service.preflight_draft(
            branch_id,
            source_chapter_index=3,
            draft=draft,
            comparison=comparison,
            skill_outputs={
                "_gate_meta": {"overall_verdict": "needs_revision"},
                "_risk_meta": {"overall_risk_level": "medium"},
                "draft-self-check": {"blocking_issues": ["draft_too_short_for_gate"], "recommended_actions": []},
                "style-calibrator": {
                    "style_axes": [],
                    "style_issues": ["prose_density_thin"],
                    "prose_density_label": "thin",
                    "recommended_actions": ["补齐文风轴与句密度。"],
                },
            },
        )
        actions = service._sorted_actions(  # noqa: SLF001
            service._recommended_actions(preflight, service.chapter_imitation.review_draft(branch_id, source_chapter_index=3, draft=draft), gate, risk)  # noqa: SLF001
        )
        assert actions == sorted(
            actions,
            key=lambda item: (
                item.priority,
                service._family_sort_rank(item.action_type),  # noqa: SLF001
                {"high": 0, "medium": 1, "low": 2}.get(item.severity, 3),
                item.action_type,
                item.target,
            ),
        )
        final_verdict, stop_reason = service._aggregate_stop_reason(  # noqa: SLF001
            preflight=preflight,
            gate=gate,
            risk=risk,
            score=score,
            actions=actions,
        )
        assert final_verdict == "needs_revision"
        assert stop_reason in {"critical_action_required", "gate_revision_required", "risk_revision_required"}
        summary = service._policy_summary(  # noqa: SLF001
            preflight=preflight,
            gate=gate,
            risk=risk,
            score=score,
            actions=actions,
            final_verdict=final_verdict,
            stop_reason=stop_reason,
        )
        assert summary["highest_action_priority"] == min(item.priority for item in actions)
        assert "weak_lane_action_count" in summary
        assert "reader_sim" in summary["issue_families"] or "style" in summary["issue_families"]


def test_aggregate_stop_reason_p1_medium_does_not_veto_quality_pass() -> None:
    """P1 actions with severity=medium are advisory; if gate/risk/score are clean, allow pass.

    Production data showed 297/297 chapters had P1+medium 'expand_middle:draft_body' style
    advisory actions. Old logic vetoed all of them. Tuned threshold lets quality_pass through
    when the substantive checks (gate/risk/score) all clear.
    """
    from novel_analyzer.domain.schemas import (
        ChapterImitationGateReport,
        ChapterImitationHarnessAction,
        ChapterImitationPreflightReport,
        ChapterImitationRiskReport,
        ChapterImitationScoreReport,
    )

    preflight = ChapterImitationPreflightReport(
        source_chapter_index=1,
        draft_title="t",
        overall_verdict="warn",
        blocking_issues=[],
    )
    gate = ChapterImitationGateReport(
        source_chapter_index=1,
        draft_title="t",
        overall_verdict="aligned_but_needs_revision",
    )
    risk = ChapterImitationRiskReport(
        source_chapter_index=1,
        draft_title="t",
        overall_risk_level="low",
    )
    score = ChapterImitationScoreReport(
        source_chapter_index=1,
        draft_title="t",
        structure_score=82,
        style_alignment_score=82,
        risk_score=85,
        overall_score=83,
    )
    p1_medium_actions = [
        ChapterImitationHarnessAction(
            action_type="repair_rhythm", target="rhythm",
            severity="medium", priority=1,
        ),
        ChapterImitationHarnessAction(
            action_type="reinforce_ending_hook", target="ending_hook",
            severity="medium", priority=2,
        ),
    ]
    verdict, reason = HarnessControllerService._aggregate_stop_reason(  # noqa: SLF001
        preflight=preflight, gate=gate, risk=risk, score=score, actions=p1_medium_actions,
    )
    assert verdict == "pass"
    assert reason == "harness_soft_pass"


def test_aggregate_stop_reason_p1_high_still_vetoes() -> None:
    """P1 with severity=high (e.g. 'expand_middle' on too-short draft) MUST still block."""
    from novel_analyzer.domain.schemas import (
        ChapterImitationGateReport,
        ChapterImitationHarnessAction,
        ChapterImitationPreflightReport,
        ChapterImitationRiskReport,
        ChapterImitationScoreReport,
    )

    preflight = ChapterImitationPreflightReport(
        source_chapter_index=1, draft_title="t", overall_verdict="warn",
    )
    gate = ChapterImitationGateReport(
        source_chapter_index=1, draft_title="t",
        overall_verdict="aligned_but_needs_revision",
    )
    risk = ChapterImitationRiskReport(source_chapter_index=1, draft_title="t")
    score = ChapterImitationScoreReport(
        source_chapter_index=1, draft_title="t",
        structure_score=82, style_alignment_score=82, risk_score=85, overall_score=83,
    )
    high_actions = [
        ChapterImitationHarnessAction(
            action_type="expand_middle", target="draft_body",
            severity="high", priority=1,
        ),
    ]
    verdict, reason = HarnessControllerService._aggregate_stop_reason(  # noqa: SLF001
        preflight=preflight, gate=gate, risk=risk, score=score, actions=high_actions,
    )
    assert verdict == "needs_revision"
    assert reason == "critical_action_required"


def test_apply_actions_to_draft_does_not_pollute_draft_text() -> None:
    """P0-1 fix: action_queue lives in a structured field, not draft_text."""
    from novel_analyzer.domain.schemas import (
        ChapterImitationDraft,
        ChapterImitationGateReport,
        ChapterImitationHarnessAction,
        ChapterImitationPreflightReport,
        ChapterImitationReviewReport,
        ChapterImitationRiskReport,
    )

    base = ChapterImitationDraft(
        source_chapter_index=1, original_title="原", draft_title="原",
        draft_text="正文段落，没有调试痕迹。",
    )

    def reviser(d: ChapterImitationDraft, *, review: ChapterImitationReviewReport) -> ChapterImitationDraft:
        return d

    review = ChapterImitationReviewReport(
        source_chapter_index=1, original_title="原", draft_title="原",
    )
    preflight = ChapterImitationPreflightReport(source_chapter_index=1, draft_title="原")
    actions = [
        ChapterImitationHarnessAction(
            action_type="repair_rhythm", target="rhythm",
            severity="medium", priority=2,
        ),
    ]
    out = HarnessControllerService._apply_actions_to_draft(  # noqa: SLF001
        base, review=review, preflight=preflight, actions=actions, base_reviser=reviser,
    )
    assert "【Harness Action Queue】" not in out.draft_text
    assert "[P2|medium]" not in out.draft_text
    assert len(out.action_queue) == 1
    assert out.action_queue[0].action_type == "repair_rhythm"
    assert out.action_queue[0].priority == 2
