import json
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch
from typer.testing import CliRunner

from novel_analyzer.cli.app import app
from typing import Any
from tests.cli_test_support import patch_cli_sqlite_runtime

runner = CliRunner()


def test_cli_inspect_novel(tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n第1章 一\n正文\n第2章 二\n正文\n", encoding="utf-8")

    result = runner.invoke(app, ["inspect-novel", str(novel_path)])
    assert result.exit_code == 0
    assert "raw_heading_count=3" in result.stdout
    assert "normalized_chapter_count=2" in result.stdout


def test_cli_ingest_and_start_run(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n第2章 二\n正文\n", encoding="utf-8")

    _engine, _factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    init = runner.invoke(app, ["init-db", "--database-url", db_url])
    assert init.exit_code == 0

    ingest = runner.invoke(app, ["ingest", str(novel_path), "--database-url", db_url])
    assert ingest.exit_code == 0
    lines = dict(line.split("=", 1) for line in ingest.stdout.strip().splitlines())

    start = runner.invoke(
        app,
        ["start-run", lines["novel_id"], lines["manifest_id"], "--database-url", db_url],
    )
    assert start.exit_code == 0
    assert "run_id=" in start.stdout
    assert "branch_id=" in start.stdout


def test_cli_ingest_chapter_list(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    chapter_list_path = tmp_path / "chapters.json"
    chapter_list_path.write_text(
        json.dumps(
            {
                "chapters": [
                    {"title": "青华", "content": "布衣少年捡到黑牌。"},
                    {"title": "厌物丽人同行", "content": "青旒与小六子互动。"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    _engine, _factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    init = runner.invoke(app, ["init-db", "--database-url", db_url])
    assert init.exit_code == 0

    ingest = runner.invoke(
        app,
        ["ingest-chapter-list", str(chapter_list_path), "--title", "章节列表示例", "--database-url", db_url],
    )
    assert ingest.exit_code == 0
    assert "novel_id=" in ingest.stdout
    assert "manifest_id=" in ingest.stdout
    assert "chapter_count=2" in ingest.stdout
    assert "source_path=" in ingest.stdout


def test_cli_plan_next_chapter_and_imitate_chapter(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    from novel_analyzer.database.models import (
        AnalysisRun,
        ChapterArtifact,
        ChapterManifest,
        ChapterSegment,
        FactRecord,
        NovelSource,
        RunBranch,
    )
    from sqlalchemy.orm import Session

    _engine, factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    init = runner.invoke(app, ["init-db", "--database-url", db_url])
    assert init.exit_code == 0

    source_path = tmp_path / "novel.txt"
    text = (
        "第1章 大器晚成\n卫图觉醒命格并决定寻找养生功。\n"
        "第2章 二姑卫荭\n卫图拜访二姑，为资源铺垫。\n"
        "第3章 养生功法\n卫图求得龟息养气功并开始修炼。\n"
    )
    source_path.write_text(text, encoding="utf-8")

    with factory() as session:
        session = Session(bind=session.bind, future=True)
        novel = NovelSource(
            id="novel-cli-1",
            title="示例小说",
            source_path=str(source_path),
            source_hash="hash",
            metadata_json={},
        )
        manifest = ChapterManifest(
            id="manifest-cli-1",
            novel_id=novel.id,
            version=1,
            splitter_version="heuristic-v1",
            chapter_count=3,
            notes={},
        )
        run = AnalysisRun(
            id="run-cli-1",
            novel_id=novel.id,
            manifest_id=manifest.id,
            llm_base_url="https://example.invalid/v1",
            llm_model_name="gpt-5.4-mini",
            analysis_profile={},
            active_branch_id="branch-cli-1",
        )
        branch = RunBranch(
            id="branch-cli-1",
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

    plan_result = runner.invoke(
        app,
        [
            "plan-next-chapter",
            "branch-cli-1",
            "推进卫图获取养生功的机会",
            "--emphasis",
            "主线推进,资源获取",
            "--forbidden-move",
            "不要让卫图直接获得超出铺垫的力量",
            "--database-url",
            db_url,
        ],
    )
    assert plan_result.exit_code == 0
    assert '"chapter_goal"' in plan_result.stdout
    assert '"scene_plan"' in plan_result.stdout

    imitate_result = runner.invoke(
        app,
        [
            "imitate-chapter",
            "branch-cli-1",
            "3",
            "延续主角获得功法后的行动线，并保持克制成长节奏",
            "--database-url",
            db_url,
        ],
    )
    assert imitate_result.exit_code == 0
    assert '"draft_text"' in imitate_result.stdout
    assert '"comparison_notes"' in imitate_result.stdout

    compare_result = runner.invoke(
        app,
        [
            "compare-imitation",
            "branch-cli-1",
            "3",
            "延续主角获得功法后的行动线，并保持克制成长节奏",
            "--database-url",
            db_url,
        ],
    )
    assert compare_result.exit_code == 0
    assert '"comparison"' in compare_result.stdout
    assert '"overall_verdict"' in compare_result.stdout

    review_result = runner.invoke(
        app,
        [
            "review-imitation",
            "branch-cli-1",
            "3",
            "延续主角获得功法后的行动线，并保持克制成长节奏",
            "--database-url",
            db_url,
        ],
    )
    assert review_result.exit_code == 0
    assert '"review"' in review_result.stdout
    assert '"gate"' in review_result.stdout
    assert '"risk"' in review_result.stdout
    assert '"revised_draft"' in review_result.stdout

    iterate_result = runner.invoke(
        app,
        [
            "iterate-imitation",
            "branch-cli-1",
            "3",
            "延续主角获得功法后的行动线，并保持克制成长节奏",
            "--max-rounds",
            "2",
            "--database-url",
            db_url,
        ],
    )
    assert iterate_result.exit_code == 0
    assert '"rounds"' in iterate_result.stdout


def test_writer_imitate_and_range_write_output_files(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    _engine, _factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')

    runner.invoke(app, ['init-db', '--database-url', db_url])
    ingest = runner.invoke(app, ['ingest', str(novel_path), '--database-url', db_url])
    lines = dict(line.split('=', 1) for line in ingest.stdout.strip().splitlines())
    start = runner.invoke(
        app,
        ['start-run', lines['novel_id'], lines['manifest_id'], '--database-url', db_url],
    )
    run_lines = dict(line.split('=', 1) for line in start.stdout.strip().splitlines())

    class _FakeReport:
        def model_dump(self, mode: str = "json") -> dict[str, Any]:
            _ = mode
            return {
                "final_verdict": "needs_revision",
                "stop_reason": "critical_action_required",
                "policy_summary": {"highest_action_priority": 1},
                "action_queue": [
                    {"priority": 1, "severity": "medium", "action_type": "repair_hook", "target": "ending_hook"}
                ],
                "rounds": [
                    {
                        "comparison": {
                            "original_title": "原章标题",
                            "draft_title": "仿写标题",
                            "source_length": 1000,
                            "draft_length": 900,
                            "structure_overlap_notes": ["结构基本对齐"],
                            "style_alignment_notes": ["文风需要再收紧"],
                            "risk_alignment_notes": ["关注 OOC 风险"],
                        },
                        "skill_outputs": {
                            "reader-sim-review": {
                                "reader_profile": "core_web_novel_reader",
                                "engagement_score": 61,
                                "concerns": ["reader_hook_weak"],
                                "recommended_actions": ["增强章尾期待感"],
                            }
                        },
                    }
                ],
                "final_draft": {
                    "draft_title": "仿写标题",
                    "draft_text": "仿写正文\n\n【Harness Action Queue】\n[P1|medium] repair_rhythm:rhythm",
                    "risk_gate_notes": ["检查 OOC", "检查 OOC"],
                },
            }

    seen: dict[str, Any] = {}

    class _FakeHarnessService:
        def run_harness(
            self,
            branch_id: str,
            source_chapter_index: int,
            target_goal: str,
            max_rounds: int,
            use_llm: bool,
            model_name: str | None,
            steering_pack: dict[str, list[str]] | None = None,
        ) -> _FakeReport:
            seen["steering_pack"] = steering_pack
            _ = branch_id, source_chapter_index, target_goal, max_rounds, use_llm, model_name
            return _FakeReport()

    monkeypatch.setattr('novel_analyzer.cli.app._imitation_harness_service', lambda session, settings: _FakeHarnessService())
    monkeypatch.setattr(
        'novel_analyzer.cli.app.SteeringLibraryService',
        lambda: type(
            '_FakeSteeringLibraryService',
            (),
            {
                'assemble_pack': staticmethod(
                    lambda **kwargs: {
                        'worldview_capsule': ['灵气不是无限资源，而是与身份和税制绑定'] if kwargs.get('worldview_docs') else [],
                        'trope_axes': ['底层逆袭'] if kwargs.get('trope_docs') else [],
                        'innovation_directives': ['让每次进步带来身份/资源/关系变化'] if kwargs.get('audience_docs') else [],
                        'taboo_innovations': [],
                        'external_knowledge_refs': ['章尾最好有更高层级机会或压力'] if kwargs.get('audience_docs') else [],
                    }
                ),
                'retrieve_pack': staticmethod(
                    lambda **kwargs: {
                        'steering_pack': {
                            'worldview_capsule': ['灵气不是无限资源，而是与身份和税制绑定'] if kwargs.get('worldview_docs') else [],
                            'trope_axes': ['底层逆袭'] if kwargs.get('trope_docs') else [],
                            'innovation_directives': ['让每次进步带来身份/资源/关系变化'] if kwargs.get('audience_docs') else [],
                            'taboo_innovations': [],
                            'external_knowledge_refs': ['章尾最好有更高层级机会或压力'] if kwargs.get('audience_docs') else [],
                        },
                        'retrieval_meta': {
                            'query_text': kwargs.get('query_text', ''),
                            'selected_trope_docs': kwargs.get('trope_docs', [])[:2],
                            'selected_worldview_docs': kwargs.get('worldview_docs', [])[:2],
                            'selected_audience_docs': kwargs.get('audience_docs', [])[:2],
                            'hit_reasons': {'trope': {}, 'worldview': {}, 'audience': {}},
                            'selected_doc_summaries': {
                                'trope': [
                                    {
                                        'slug': slug,
                                        'labels': ['底层逆袭'],
                                        'summary': '标签：底层逆袭；套路轴：底层逆袭',
                                        'trope_axes': ['底层逆袭'],
                                    }
                                    for slug in kwargs.get('trope_docs', [])[:2]
                                ],
                                'worldview': [
                                    {
                                        'slug': slug,
                                        'labels': ['税制化世界观'],
                                        'summary': '标签：税制化世界观；世界观：灵气不是无限资源，而是与身份和税制绑定',
                                        'worldview_capsule': ['灵气不是无限资源，而是与身份和税制绑定'],
                                    }
                                    for slug in kwargs.get('worldview_docs', [])[:2]
                                ],
                                'audience': [
                                    {
                                        'slug': slug,
                                        'labels': ['商业钩子'],
                                        'summary': '标签：商业钩子；读者/应用提示：章尾最好有更高层级机会或压力',
                                        'external_knowledge_refs': ['章尾最好有更高层级机会或压力'],
                                    }
                                    for slug in kwargs.get('audience_docs', [])[:2]
                                ],
                            },
                        },
                    }
                ),
            },
        )()
    )
    output_dir = tmp_path / 'writer-output'

    result = runner.invoke(
        app,
        [
            'writer-imitate', run_lines['branch_id'], '1', '延续主线',
            '--worldview-note', '灵气稀薄，身份资源强绑定',
            '--trope-axis', '底层逆袭',
            '--innovation-directive', '把修炼收益折算为社会信用',
            '--output-dir', str(output_dir), '--database-url', db_url
        ],
    )
    assert result.exit_code == 0
    assert (output_dir / 'writer-imitate-ch1.json').exists()
    assert (output_dir / 'writer-imitate-ch1.md').exists()
    md_text = (output_dir / 'writer-imitate-ch1.md').read_text(encoding='utf-8')
    assert '【Harness Action Queue】' not in md_text
    assert md_text.count('检查 OOC') == 1
    assert '灵气稀薄，身份资源强绑定' in seen["steering_pack"]["worldview_capsule"]

    result = runner.invoke(
        app,
        ['writer-imitate-range', run_lines['branch_id'], '3:延续主线', '4:制造新阻力', '--output-dir', str(output_dir), '--database-url', db_url],
    )
    assert result.exit_code == 0
    assert (output_dir / 'writer-imitate-range-3-4.json').exists()
    assert (output_dir / 'writer-imitate-range-3-4.md').exists()
    range_payload = json.loads((output_dir / 'writer-imitate-range-3-4.json').read_text(encoding='utf-8'))
    assert 'steering_pack' in range_payload

    result = runner.invoke(
        app,
        ['writer-imitate-review', run_lines['branch_id'], '1', '延续主线', '--output-dir', str(output_dir), '--database-url', db_url],
    )
    assert result.exit_code == 0
    review_md = output_dir / 'writer-imitate-review-ch1.md'
    assert review_md.exists()
    review_text = review_md.read_text(encoding='utf-8')
    assert '## Draft Text' in review_text
    assert '【Harness Action Queue】' not in review_text
    assert '## Side-by-side Review' in review_text
    assert '## Action Queue' in review_text

    result = runner.invoke(
        app,
        ['writer-imitate-index', '--output-dir', str(output_dir)],
    )
    assert result.exit_code == 0
    index_md = output_dir / 'writer-imitate-index.md'
    assert index_md.exists()
    index_text = index_md.read_text(encoding='utf-8')
    assert 'writer-imitate-range-3-4.json' in index_text
    assert 'chapter 3' in index_text

    result = runner.invoke(
        app,
        [
            'writer-innovation-experiment',
            run_lines['branch_id'],
            'batch-a',
            '3:延续主线',
            '4:制造新阻力',
            '--trope-doc', 'xianxia-underdog-ledger',
            '--worldview-doc', 'aura-decline-tax-state',
            '--audience-doc', 'male-xianxia-commercial-hooks',
            '--output-dir', str(output_dir),
            '--database-url', db_url,
        ],
    )
    assert result.exit_code == 0
    experiment_json = output_dir / 'writer-innovation-experiment-batch-a.json'
    experiment_md = output_dir / 'writer-innovation-experiment-batch-a.md'
    assert experiment_json.exists()
    assert experiment_md.exists()
    experiment_payload = json.loads(experiment_json.read_text(encoding='utf-8'))
    assert experiment_payload['contract_version'] == 'writer-innovation-experiment.v1'
    assert '底层逆袭' in experiment_payload['steering_pack']['trope_axes']
    assert experiment_payload['experiment_meta']['chapter_count'] == 2
    assert experiment_payload['steering_retrieval_meta']['selected_trope_docs'] == ['xianxia-underdog-ledger']
    trope_doc_summaries = experiment_payload['steering_retrieval_meta']['selected_doc_summaries']['trope']
    assert trope_doc_summaries[0]['slug'] == 'xianxia-underdog-ledger'
    assert trope_doc_summaries[0]['summary']
    baseline_vs_steering_report = experiment_payload['experiment_meta']['baseline_vs_steering_report']
    assert baseline_vs_steering_report['chapter_count'] == 2
    delta_visual_summary = experiment_payload['delta_visual_summary']
    assert delta_visual_summary['innovation_card']['level']
    assert delta_visual_summary['risk_card']['level']
    reader_sim_acceptance_summary = experiment_payload['reader_sim_acceptance_summary']
    assert reader_sim_acceptance_summary['chapter_count'] == 2
    assert 'average_score_delta' in reader_sim_acceptance_summary
    writer_innovation_explanation = experiment_payload['writer_innovation_explanation']
    assert writer_innovation_explanation['summary']
    assert writer_innovation_explanation['focus']
    experiment_decision_note = experiment_payload['experiment_decision_note']
    assert experiment_decision_note['recommendation']
    assert experiment_decision_note['next_action']
    assert experiment_decision_note['pilot_scope']
    assert experiment_decision_note['promotion_gate']
    assert experiment_decision_note['rollback_trigger']
    assert experiment_decision_note['evidence_required']
    assert 'confidence_level' in experiment_decision_note
    assert 'business_risk_label' in experiment_decision_note
    assert 'go_live_checklist' in experiment_decision_note
    assert 'success_kpi_targets' in experiment_decision_note
    assert 'failure_kpi_triggers' in experiment_decision_note
    assert 'observation_window' in experiment_decision_note
    assert 'owner_roles' in experiment_decision_note
    assert 'handoff_packet' in experiment_decision_note
    assert len(experiment_payload['baseline_items']) == 2
    assert 'innovation_delta_summary' in experiment_payload['experiment_meta']
    assert 'risk_delta_summary' in experiment_payload['experiment_meta']
    experiment_text = experiment_md.read_text(encoding='utf-8')
    assert '## Steering Retrieval Meta' in experiment_text
    assert '### Hit Reasons' in experiment_text
    assert '### Hit Doc Summaries' in experiment_text
    assert '## Delta Visual Summary' in experiment_text
    assert '### innovation_card' in experiment_text
    assert '### risk_card' in experiment_text
    assert '## Reader Sim Acceptance Summary' in experiment_text
    assert '### Reader Sim Acceptance' in experiment_text
    assert '## Writer Innovation Explanation' in experiment_text
    assert '## Experiment Decision Note' in experiment_text
    assert 'pilot_scope:' in experiment_text
    assert 'rollback_trigger:' in experiment_text
    assert 'confidence_level:' in experiment_text
    assert 'go_live_checklist:' in experiment_text
    assert 'observation_window:' in experiment_text
    assert 'success_kpi_targets:' in experiment_text
    assert '### Baseline vs Steering' in experiment_text
    assert 'xianxia-underdog-ledger: 标签：底层逆袭；套路轴：底层逆袭' in experiment_text

    result = runner.invoke(
        app,
        ['writer-imitate-index', '--output-dir', str(output_dir)],
    )
    assert result.exit_code == 0
    index_text = index_md.read_text(encoding='utf-8')
    assert '## Innovation Experiments' in index_text
    assert 'writer-innovation-experiment-batch-a.json' in index_text
    assert 'reader_acceptance: improved=' in index_text
    assert 'baseline_vs_steering:' in index_text
    assert '## Experiment Session Control Plane' in index_text
    assert 'promotion_verdict:' in index_text
    assert 'risk_register:' in index_text
    assert 'handoff_summary:' in index_text
    assert 'session_ship_decision:' in index_text
    assert 'session_required_review:' in index_text
    assert 'session_owner_handoff:' in index_text
    assert 'session_priority_queue:' in index_text
    assert 'session_lane_status:' in index_text
    assert 'session_escalation_path:' in index_text
    assert 'session_release_readiness:' in index_text
    assert 'session_recovery_plan:' in index_text
    assert 'session_command_brief:' in index_text
    assert 'session_execution_mode:' in index_text
    assert 'session_action_window:' in index_text
    assert 'session_recovery_owner:' in index_text
    assert 'session_runtime_contract:' in index_text
    assert 'session_state_snapshot:' in index_text
    assert 'session_transition_rules:' in index_text
    assert 'session_auto_actions:' in index_text
    assert 'session_manual_overrides:' in index_text
    assert 'session_guard_conditions:' in index_text
    assert 'session_entry_criteria:' in index_text
    assert 'session_exit_criteria:' in index_text
    assert 'session_auto_escalations:' in index_text
    assert 'session_override_audit:' in index_text
    assert 'session_state_machine:' in index_text
    assert 'session_allowed_transitions:' in index_text
    assert 'session_trigger_matrix:' in index_text
    assert 'session_reconciliation_steps:' in index_text
    assert 'session_operator_commands:' in index_text
    assert 'session_policy_pack:' in index_text
    assert 'session_slo_contract:' in index_text
    assert 'session_failure_domains:' in index_text
    assert 'session_intervention_matrix:' in index_text
    assert 'session_audit_digest:' in index_text
    assert 'session_governor_mode:' in index_text
    assert 'session_decision_bus:' in index_text
    assert 'session_watchdog_rules:' in index_text
    assert 'session_contingency_routes:' in index_text
    assert 'session_operating_envelope:' in index_text
    assert 'session_control_objectives:' in index_text
    assert 'session_enforcement_rules:' in index_text
    assert 'session_decision_priorities:' in index_text
    assert 'session_supervision_hooks:' in index_text
    assert 'session_telemetry_digest:' in index_text
    assert 'session_policy_versions:' in index_text
    assert 'session_safety_budget:' in index_text
    assert 'session_latency_budget:' in index_text
    assert 'session_review_quorum:' in index_text
    assert 'session_contract_digest:' in index_text
    assert 'session_compliance_pack:' in index_text
    assert 'session_failure_budget:' in index_text
    assert 'session_override_budget:' in index_text
    assert 'session_reliability_digest:' in index_text
    assert 'session_governance_checksum:' in index_text
    assert '## Experiment Ledger' in index_text
    assert '### batch-a' in index_text
    assert 'focus:' in index_text
    assert 'recommendation:' in index_text
    assert 'next_action:' in index_text
    assert 'pilot_scope:' in index_text
    assert 'confidence_level:' in index_text
    assert 'observation_window:' in index_text
    assert 'business_risk_label:' in index_text


def test_writer_output_markdown_skips_empty_hit_doc_summaries(tmp_path: Path) -> None:
    from novel_analyzer.cli.app import _write_writer_imitation_outputs

    output_dir = tmp_path / "writer-output-empty-hit-doc-summaries"
    payload = {
        "steering_retrieval_meta": {
            "selected_trope_docs": [],
            "selected_worldview_docs": [],
            "selected_audience_docs": [],
            "hit_reasons": {"trope": {}, "worldview": {}, "audience": {}},
            "selected_doc_summaries": {"trope": [], "worldview": [], "audience": []},
        },
        "final_draft": {"draft_title": "", "draft_text": "", "risk_gate_notes": []},
    }
    _json_path, md_path = _write_writer_imitation_outputs(output_dir, "empty-hit-doc-summaries", payload)
    md_text = md_path.read_text(encoding="utf-8")
    assert "### Hit Doc Summaries" not in md_text
