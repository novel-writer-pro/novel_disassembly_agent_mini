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
    session_state_json = output_dir / 'writer-imitate-session-state.json'
    operator_surface_json = output_dir / 'writer-imitate-operator-surface.json'
    operator_surface_md = output_dir / 'writer-imitate-operator-surface.md'
    legacy_surface_json = output_dir / 'writer-imitate-legacy-contract-surface.json'
    legacy_surface_md = output_dir / 'writer-imitate-legacy-contract-surface.md'
    legacy_retirement_preview_json = output_dir / 'writer-imitate-legacy-retirement-preview.json'
    legacy_retirement_preview_md = output_dir / 'writer-imitate-legacy-retirement-preview.md'
    control_surface_registry_json = output_dir / 'writer-imitate-control-surface-registry.json'
    control_surface_registry_md = output_dir / 'writer-imitate-control-surface-registry.md'
    action_queue_json = output_dir / 'writer-imitate-action-queue.json'
    action_queue_md = output_dir / 'writer-imitate-action-queue.md'
    execution_state_json = output_dir / 'writer-imitate-execution-state.json'
    execution_state_md = output_dir / 'writer-imitate-execution-state.md'
    execution_replay_json = output_dir / 'writer-imitate-execution-replay.json'
    execution_replay_md = output_dir / 'writer-imitate-execution-replay.md'
    execution_apply_json = output_dir / 'writer-imitate-execution-apply.json'
    execution_apply_md = output_dir / 'writer-imitate-execution-apply.md'
    live_control_state_json = output_dir / 'writer-imitate-live-control-state.json'
    live_control_state_md = output_dir / 'writer-imitate-live-control-state.md'
    live_mutation_preview_json = output_dir / 'writer-imitate-live-mutation-preview.json'
    live_mutation_preview_md = output_dir / 'writer-imitate-live-mutation-preview.md'
    live_checkpoint_state_json = output_dir / 'writer-imitate-live-checkpoint-state.json'
    live_checkpoint_state_md = output_dir / 'writer-imitate-live-checkpoint-state.md'
    live_transition_state_json = output_dir / 'writer-imitate-live-transition-state.json'
    live_transition_state_md = output_dir / 'writer-imitate-live-transition-state.md'
    live_validation_state_json = output_dir / 'writer-imitate-live-validation-state.json'
    live_validation_state_md = output_dir / 'writer-imitate-live-validation-state.md'
    execution_resume_json = output_dir / 'writer-imitate-execution-resume.json'
    execution_resume_md = output_dir / 'writer-imitate-execution-resume.md'
    assert index_md.exists()
    assert session_state_json.exists()
    assert operator_surface_json.exists()
    assert operator_surface_md.exists()
    assert legacy_surface_json.exists()
    assert legacy_surface_md.exists()
    assert legacy_retirement_preview_json.exists()
    assert legacy_retirement_preview_md.exists()
    assert control_surface_registry_json.exists()
    assert control_surface_registry_md.exists()
    assert action_queue_json.exists()
    assert action_queue_md.exists()
    assert execution_state_json.exists()
    assert execution_state_md.exists()
    assert execution_replay_json.exists()
    assert execution_replay_md.exists()
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
    assert '### Control Surface EntryPoints' in index_text
    assert 'legacy_retirement_preview: writer-imitate-legacy-retirement-preview.md' in index_text
    assert 'live_control_state: writer-imitate-live-control-state.md' in index_text
    assert 'live_mutation_preview: writer-imitate-live-mutation-preview.md' in index_text
    assert 'primary_operator_role: default-operator-home' in index_text
    assert 'live_control_state_role: preview-to-live-bridge-surface' in index_text
    assert 'live_mutation_preview_role: live-mutation-review-surface' in index_text
    assert 'display_policy: primary-first-legacy-secondary' in index_text
    assert '### Operator-Facing Stable Contract' in index_text
    assert '### Full Session Field Surface' in index_text
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
    assert 'session_authority_map:' in index_text
    assert 'session_escalation_budget:' in index_text
    assert 'session_remediation_contract:' in index_text
    assert 'session_consensus_rules:' in index_text
    assert 'session_integrity_digest:' in index_text
    assert 'session_control_memory:' in index_text
    assert 'session_constraint_register:' in index_text
    assert 'session_safety_invariants:' in index_text
    assert 'session_repair_budget:' in index_text
    assert 'session_runtime_digest:' in index_text
    assert 'session_control_fabric:' in index_text
    assert 'session_guardrail_matrix:' in index_text
    assert 'session_override_protocol:' in index_text
    assert 'session_failure_isolation:' in index_text
    assert 'session_runtime_manifest:' in index_text
    assert 'session_control_bus:' in index_text
    assert 'session_event_channels:' in index_text
    assert 'session_runtime_priorities:' in index_text
    assert 'session_alert_routes:' in index_text
    assert 'session_state_checkpoint:' in index_text
    assert 'session_execution_graph:' in index_text
    assert 'session_signal_registry:' in index_text
    assert 'session_action_contract:' in index_text
    assert 'session_backpressure_rules:' in index_text
    assert 'session_runtime_proof:' in index_text
    assert 'session_supervisory_contract:' in index_text
    assert 'session_recovery_matrix:' in index_text
    assert 'session_signal_budget:' in index_text
    assert 'session_checkpoint_policy:' in index_text
    assert 'session_operating_ledger:' in index_text
    assert 'session_governance_fabric:' in index_text
    assert 'session_checkpoint_contract:' in index_text
    assert 'session_supervision_priorities:' in index_text
    assert 'session_ledger_consistency_rules:' in index_text
    assert 'session_runtime_attestation:' in index_text
    assert 'session_runtime_mesh:' in index_text
    assert 'session_policy_router:' in index_text
    assert 'session_checkpoint_ring:' in index_text
    assert 'session_audit_stream:' in index_text
    assert 'session_operating_signature:' in index_text
    assert 'session_policy_mesh:' in index_text
    assert 'session_enforcement_bus:' in index_text
    assert 'session_runtime_sentry:' in index_text
    assert 'session_checkpoint_audit_chain:' in index_text
    assert 'session_operating_posture:' in index_text
    assert 'session_attestation_chain:' in index_text
    assert 'session_trust_zones:' in index_text
    assert 'session_policy_attestors:' in index_text
    assert 'session_recovery_posture:' in index_text
    assert '#### Legacy Verdict/Digest Compatibility Layer' in index_text
    assert 'session_control_verdict:' in index_text
    assert 'session_protocol_stack:' in index_text
    assert 'session_trust_contract:' in index_text
    assert 'session_recovery_authority:' in index_text
    assert 'session_audit_checkpoint_map:' in index_text
    assert 'session_runtime_certificate:' in index_text
    assert 'session_governance_topology:' in index_text
    assert 'session_protocol_budget:' in index_text
    assert 'session_certificate_chain:' in index_text
    assert 'session_recovery_authorizations:' in index_text
    assert 'session_control_attestation:' in index_text
    assert 'session_assurance_contract:' in index_text
    assert 'session_policy_checksum:' in index_text
    assert 'session_runtime_alignment:' in index_text
    assert 'session_recovery_certainty:' in index_text
    assert 'session_operator_assurance:' in index_text
    assert 'session_meta_governor:' in index_text
    assert 'session_policy_integrity:' in index_text
    assert 'session_runtime_consistency:' in index_text
    assert 'session_override_accountability:' in index_text
    assert 'session_control_confidence:' in index_text
    assert 'session_executive_contract:' in index_text
    assert 'session_supervision_certificate:' in index_text
    assert 'session_override_liability:' in index_text
    assert 'session_operating_authority:' in index_text
    assert 'session_authority_certificate:' in index_text
    assert 'session_policy_envelope:' in index_text
    assert 'session_escalation_authority:' in index_text
    assert 'session_assurance_digest:' in index_text
    assert 'session_governance_verdict:' in index_text
    assert 'session_governance_mesh:' in index_text
    assert 'session_attestation_budget:' in index_text
    assert 'session_policy_fallbacks:' in index_text
    assert 'session_recovery_routing:' in index_text
    assert 'session_runtime_verdict:' in index_text
    assert 'session_control_plane_closure:' in index_text
    assert 'session_exec_fabric:' in index_text
    assert 'session_authority_routes:' in index_text
    assert 'session_assurance_chain:' in index_text
    assert 'session_runtime_seal:' in index_text
    assert 'session_authority_fabric:' in index_text
    assert 'session_override_chain:' in index_text
    assert 'session_control_closure_audit:' in index_text
    assert 'session_runtime_witness:' in index_text
    assert 'session_governance_posture:' in index_text
    assert 'session_operating_charter:' in index_text
    assert 'session_control_charter:' in index_text
    assert 'session_governance_charter:' in index_text
    assert 'session_runtime_authority_digest:' in index_text
    assert 'session_final_control_verdict:' in index_text
    assert 'session_command_mesh:' in index_text
    assert 'session_authority_fabric_v2:' in index_text
    assert 'session_closure_attestation:' in index_text
    assert 'session_operating_charter_mesh:' in index_text
    assert 'session_final_runtime_verdict:' in index_text
    assert 'session_governance_backbone:' in index_text
    assert 'session_control_lattice:' in index_text
    assert 'session_authority_bus:' in index_text
    assert 'session_runtime_witness_chain:' in index_text
    assert 'session_os_control_digest:' in index_text
    assert 'session_executive_command_mesh:' in index_text
    assert 'session_authority_control_matrix:' in index_text
    assert 'session_runtime_closure_proof:' in index_text
    assert 'session_governance_signal_chain:' in index_text
    assert 'session_operating_system_verdict:' in index_text
    assert 'session_governance_closure:' in index_text
    assert 'session_authority_verdict:' in index_text
    assert 'session_runtime_horizon:' in index_text
    assert 'session_supervision_digest:' in index_text
    assert 'session_control_summary:' in index_text
    assert 'session_operating_system_contract:' in index_text
    assert 'session_control_checkpoint_digest:' in index_text
    assert 'session_authority_signature:' in index_text
    assert 'session_recovery_escalation_mesh:' in index_text
    assert 'session_final_operating_posture:' in index_text
    assert 'session_control_kernel:' in index_text
    assert 'session_safety_circuit_breakers:' in index_text
    assert 'session_override_channels:' in index_text
    assert 'session_repair_loops:' in index_text
    assert 'session_control_loop:' in index_text
    assert 'session_queue_registry:' in index_text
    assert 'session_execution_registry:' in index_text
    assert 'session_governance_registry:' in index_text
    assert 'session_digest_registry:' in index_text
    assert 'session_live_ops_board:' in index_text
    assert 'session_action_backlog:' in index_text
    assert 'session_transition_queue:' in index_text
    assert 'session_checkpoint_mutations:' in index_text
    assert '## Experiment Ledger' in index_text
    assert '### batch-a' in index_text
    assert 'focus:' in index_text
    assert 'recommendation:' in index_text
    assert 'next_action:' in index_text
    assert 'pilot_scope:' in index_text
    assert 'confidence_level:' in index_text
    assert 'observation_window:' in index_text
    assert 'business_risk_label:' in index_text
    session_state = json.loads(session_state_json.read_text(encoding='utf-8'))
    assert session_state['contract_version'] == 'writer-imitate-session-state.v3'
    assert 'promotion_verdict' in session_state
    assert 'session_ready_queue' in session_state
    assert 'session_blocked_queue' in session_state
    assert 'session_escalation_path' in session_state
    assert 'session_recovery_plan' in session_state
    assert session_state['session_control_loop']['entry_criteria']
    assert 'priority_queue' in session_state['session_queue_registry']
    assert session_state['session_execution_registry']['execution_mode']
    assert session_state['session_governance_registry']['governor_mode']
    assert session_state['session_digest_registry']['runtime_contract']
    assert session_state['session_live_ops_board']['session_ship_decision']
    assert session_state['session_action_backlog']
    assert session_state['session_transition_queue']
    assert session_state['session_checkpoint_mutations']
    assert session_state['session_operator_contract']['status']['session_lane_status']
    assert session_state['session_operator_contract']['queues']['priority_queue']
    assert session_state['session_operator_contract']['owners']['session_recovery_owner']
    assert session_state['session_primary_verdicts']['final_verdict']
    assert session_state['session_primary_digests']['runtime_contract']
    assert session_state['session_primary_contract_hints']['migration_status'] == 'compatibility-layer-active'
    assert session_state['session_legacy_contract_layer']['legacy_verdict_count'] > 0
    assert session_state['session_legacy_retirement_plan']['phase'] == 'pre-retirement'
    assert session_state['session_legacy_retirement_pilot_wave']['wave_id'] == 'legacy-retirement-wave-01'
    assert session_state['session_control_surface_entrypoints']['primary_operator_entrypoint_json'] == 'writer-imitate-operator-surface.json'
    assert session_state['session_control_surface_entrypoints']['legacy_retirement_preview_json'] == 'writer-imitate-legacy-retirement-preview.json'
    assert session_state['session_control_surface_entrypoints']['live_control_state_json'] == 'writer-imitate-live-control-state.json'
    assert session_state['session_control_surface_entrypoints']['live_mutation_preview_json'] == 'writer-imitate-live-mutation-preview.json'
    assert session_state['session_control_surface_entrypoints']['entrypoint_roles']['primary_operator_entrypoint'] == 'default-operator-home'
    assert session_state['session_control_surface_entrypoints']['entrypoint_roles']['live_mutation_preview'] == 'live-mutation-review-surface'
    assert session_state['session_control_surface_entrypoints']['display_policy'] == 'primary-first-legacy-secondary'
    assert session_state['experiments']
    operator_surface_payload = json.loads(operator_surface_json.read_text(encoding='utf-8'))
    assert operator_surface_payload['contract_version'] == 'writer-imitate-operator-surface.v1'
    assert operator_surface_payload['primary_operator_entrypoint'] == 'writer-imitate-operator-surface.json'
    assert operator_surface_payload['legacy_operator_entrypoint'] == 'writer-imitate-legacy-contract-surface.json'
    assert operator_surface_payload['session_operator_contract']['status']['session_execution_mode']
    assert operator_surface_payload['session_primary_verdicts']['runtime_verdict']
    assert operator_surface_payload['session_primary_digests']['operating_digest']
    assert operator_surface_payload['session_primary_contract_hints']['preferred_verdict_source'] == 'session_primary_verdicts'
    assert operator_surface_payload['session_legacy_contract_layer']['status'] == 'compatibility-layer-active'
    assert operator_surface_payload['session_control_surface_entrypoints']['legacy_operator_entrypoint_markdown'] == 'writer-imitate-legacy-contract-surface.md'
    assert operator_surface_payload['session_control_surface_entrypoints']['legacy_retirement_preview_markdown'] == 'writer-imitate-legacy-retirement-preview.md'
    assert operator_surface_payload['session_control_surface_entrypoints']['live_control_state_markdown'] == 'writer-imitate-live-control-state.md'
    assert operator_surface_payload['session_control_surface_entrypoints']['live_mutation_preview_markdown'] == 'writer-imitate-live-mutation-preview.md'
    assert operator_surface_payload['session_control_surface_entrypoints']['entrypoint_roles']['live_control_state'] == 'preview-to-live-bridge-surface'
    assert operator_surface_payload['session_control_surface_entrypoints']['entrypoint_roles']['live_mutation_preview'] == 'live-mutation-review-surface'
    assert operator_surface_payload['session_control_surface_entrypoints']['display_policy'] == 'primary-first-legacy-secondary'
    assert operator_surface_payload['session_legacy_retirement_readiness']['status'] == 'not-ready'
    assert operator_surface_payload['session_legacy_retirement_plan']['pilot_candidates']
    assert operator_surface_payload['session_legacy_retirement_pilot_wave']['target_family'] == 'extra digest/checksum variants'
    operator_surface_text = operator_surface_md.read_text(encoding='utf-8')
    assert '# Writer Imitation Operator Surface' in operator_surface_text
    assert 'legacy_operator_entrypoint: writer-imitate-legacy-contract-surface.md' in operator_surface_text
    assert 'legacy_retirement_preview: writer-imitate-legacy-retirement-preview.md' in operator_surface_text
    assert 'live_control_state: writer-imitate-live-control-state.md' in operator_surface_text
    assert 'live_mutation_preview: writer-imitate-live-mutation-preview.md' in operator_surface_text
    assert 'primary_operator_role: default-operator-home' in operator_surface_text
    assert 'display_policy: primary-first-legacy-secondary' in operator_surface_text
    assert '## Primary Verdicts' in operator_surface_text
    assert '## Primary Digests' in operator_surface_text
    assert operator_surface_text.index('## Primary Verdicts') < operator_surface_text.index('## Operator-Facing Stable Contract')
    assert '## Operator-Facing Stable Contract' in operator_surface_text
    assert '## Primary Contract Migration Hints' in operator_surface_text
    assert 'compatibility_note: legacy verdict/digest fields remain available but are no longer the preferred first-layer entrypoint' in operator_surface_text
    assert '## Legacy Contract Layer' in operator_surface_text
    assert '## Legacy Retirement Readiness' in operator_surface_text
    assert '## Legacy Retirement Plan' in operator_surface_text
    assert '## Legacy Retirement Pilot Wave' in operator_surface_text
    legacy_surface_payload = json.loads(legacy_surface_json.read_text(encoding='utf-8'))
    assert legacy_surface_payload['contract_version'] == 'writer-imitate-legacy-contract-surface.v1'
    assert legacy_surface_payload['primary_operator_entrypoint'] == 'writer-imitate-operator-surface.json'
    assert legacy_surface_payload['legacy_operator_entrypoint'] == 'writer-imitate-legacy-contract-surface.json'
    assert legacy_surface_payload['session_legacy_contract_layer']['legacy_verdict_count'] > 0
    assert legacy_surface_payload['session_control_surface_entrypoints']['primary_operator_entrypoint_markdown'] == 'writer-imitate-operator-surface.md'
    assert legacy_surface_payload['session_control_surface_entrypoints']['legacy_retirement_preview_markdown'] == 'writer-imitate-legacy-retirement-preview.md'
    assert legacy_surface_payload['session_control_surface_entrypoints']['live_control_state_markdown'] == 'writer-imitate-live-control-state.md'
    assert legacy_surface_payload['session_control_surface_entrypoints']['live_mutation_preview_markdown'] == 'writer-imitate-live-mutation-preview.md'
    assert legacy_surface_payload['session_control_surface_entrypoints']['entrypoint_roles']['legacy_operator_entrypoint'] == 'compatibility-governance-surface'
    assert legacy_surface_payload['session_control_surface_entrypoints']['display_policy'] == 'primary-first-legacy-secondary'
    assert legacy_surface_payload['session_legacy_retirement_readiness']['status'] == 'not-ready'
    assert legacy_surface_payload['session_legacy_retirement_plan']['second_wave_candidates']
    assert legacy_surface_payload['session_legacy_retirement_pilot_wave']['status'] == 'planned-not-executed'
    legacy_surface_text = legacy_surface_md.read_text(encoding='utf-8')
    assert '# Writer Imitation Legacy Contract Surface' in legacy_surface_text
    assert 'primary_operator_entrypoint: writer-imitate-operator-surface.md' in legacy_surface_text
    assert 'legacy_operator_entrypoint: writer-imitate-legacy-contract-surface.md' in legacy_surface_text
    assert 'legacy_retirement_preview: writer-imitate-legacy-retirement-preview.md' in legacy_surface_text
    assert 'legacy_operator_role: compatibility-governance-surface' in legacy_surface_text
    assert '## Legacy Contract Layer' in legacy_surface_text
    assert '## Legacy Retirement Readiness' in legacy_surface_text
    assert '## Legacy Retirement Plan' in legacy_surface_text
    assert 'session_governance_checksum_v2' in legacy_surface_text
    assert 'session_operating_checksum' in legacy_surface_text
    legacy_retirement_preview_payload = json.loads(legacy_retirement_preview_json.read_text(encoding='utf-8'))
    assert legacy_retirement_preview_payload['contract_version'] == 'writer-imitate-legacy-retirement-preview.v1'
    assert legacy_retirement_preview_payload['preview_status'] == 'planned-not-executed'
    assert legacy_retirement_preview_payload['retirement_pilot_wave']['wave_id'] == 'legacy-retirement-wave-01'
    legacy_retirement_preview_text = legacy_retirement_preview_md.read_text(encoding='utf-8')
    assert '# Writer Imitation Legacy Retirement Preview' in legacy_retirement_preview_text
    assert '## Retirement Readiness' in legacy_retirement_preview_text
    assert '## Retirement Pilot Wave' in legacy_retirement_preview_text
    assert '## Projected Effect' in legacy_retirement_preview_text
    control_surface_registry_payload = json.loads(control_surface_registry_json.read_text(encoding='utf-8'))
    assert control_surface_registry_payload['contract_version'] == 'writer-imitate-control-surface-registry.v1'
    assert control_surface_registry_payload['registry_status'] == 'active'
    assert control_surface_registry_payload['session_control_surface_entrypoints']['entrypoint_roles']['primary_operator_entrypoint'] == 'default-operator-home'
    control_surface_registry_text = control_surface_registry_md.read_text(encoding='utf-8')
    assert '# Writer Imitation Control Surface Registry' in control_surface_registry_text
    assert '## EntryPoints' in control_surface_registry_text
    assert '## EntryPoint Roles' in control_surface_registry_text
    assert '## Legacy Retirement Pilot Wave' in legacy_surface_text
    action_queue_payload = json.loads(action_queue_json.read_text(encoding='utf-8'))
    assert action_queue_payload['contract_version'] == 'writer-imitate-action-queue.v1'
    assert action_queue_payload['primary_operator_entrypoint'] == 'writer-imitate-operator-surface.json'
    assert action_queue_payload['legacy_operator_entrypoint'] == 'writer-imitate-legacy-contract-surface.json'
    assert action_queue_payload['session_operator_contract']['status']['session_execution_mode']
    assert action_queue_payload['session_primary_verdicts']['runtime_verdict']
    assert action_queue_payload['session_primary_digests']['control_summary']
    assert action_queue_payload['session_primary_contract_hints']['migration_status'] == 'compatibility-layer-active'
    assert action_queue_payload['session_legacy_contract_layer']['legacy_digest_count'] > 0
    assert action_queue_payload['action_backlog']
    assert 'execution_mode' in action_queue_payload['execution_registry']
    assert 'governor_mode' in action_queue_payload['governance_registry']
    assert action_queue_payload['transition_queue']
    assert action_queue_payload['checkpoint_mutations']
    action_queue_text = action_queue_md.read_text(encoding='utf-8')
    assert '# Writer Imitation Action Queue' in action_queue_text
    assert 'primary_operator_entrypoint: writer-imitate-operator-surface.md' in action_queue_text
    assert 'legacy_operator_entrypoint: writer-imitate-legacy-contract-surface.md' in action_queue_text
    assert '## Primary Verdicts' in action_queue_text
    assert '## Primary Digests' in action_queue_text
    assert action_queue_text.index('## Primary Verdicts') < action_queue_text.index('## Operator-Facing Stable Contract')
    assert '## Operator-Facing Stable Contract' in action_queue_text
    assert '## Primary Contract Migration Hints' in action_queue_text
    assert '## Action Backlog' in action_queue_text
    assert '## Transition Queue' in action_queue_text
    assert '## Checkpoint Mutations' in action_queue_text
    execution_state_payload = json.loads(execution_state_json.read_text(encoding='utf-8'))
    assert execution_state_payload['contract_version'] == 'writer-imitate-execution-state.v1'
    assert execution_state_payload['primary_operator_entrypoint'] == 'writer-imitate-operator-surface.json'
    assert execution_state_payload['legacy_operator_entrypoint'] == 'writer-imitate-legacy-contract-surface.json'
    assert execution_state_payload['session_operator_contract']['owners']['session_recovery_owner']
    assert execution_state_payload['session_primary_verdicts']['control_verdict']
    assert execution_state_payload['session_primary_digests']['governance_checksum']
    assert execution_state_payload['session_primary_contract_hints']['preferred_digest_source'] == 'session_primary_digests'
    assert execution_state_payload['session_legacy_contract_layer']['status'] == 'compatibility-layer-active'
    assert execution_state_payload['execution_tickets']
    assert execution_state_payload['transition_history']
    assert execution_state_payload['checkpoint_log']
    assert execution_state_payload['replay_plan']
    assert 'recovery_owner' in execution_state_payload['recovery_cursor']
    execution_state_text = execution_state_md.read_text(encoding='utf-8')
    assert '# Writer Imitation Execution State' in execution_state_text
    assert 'primary_operator_entrypoint: writer-imitate-operator-surface.md' in execution_state_text
    assert 'legacy_operator_entrypoint: writer-imitate-legacy-contract-surface.md' in execution_state_text
    assert '## Primary Verdicts' in execution_state_text
    assert '## Primary Digests' in execution_state_text
    assert execution_state_text.index('## Primary Verdicts') < execution_state_text.index('## Operator-Facing Stable Contract')
    assert '## Operator-Facing Stable Contract' in execution_state_text
    assert '## Primary Contract Migration Hints' in execution_state_text
    assert '## Execution Tickets' in execution_state_text
    assert '## Transition History' in execution_state_text
    assert '## Checkpoint Log' in execution_state_text
    assert '## Replay Plan' in execution_state_text
    assert '## Recovery Cursor' in execution_state_text
    execution_replay_payload = json.loads(execution_replay_json.read_text(encoding='utf-8'))
    assert execution_replay_payload['contract_version'] == 'writer-imitate-execution-replay.v1'
    assert execution_replay_payload['primary_operator_entrypoint'] == 'writer-imitate-operator-surface.json'
    assert execution_replay_payload['legacy_operator_entrypoint'] == 'writer-imitate-legacy-contract-surface.json'
    assert execution_replay_payload['session_operator_contract']['status']['session_ship_decision']
    assert execution_replay_payload['session_primary_verdicts']['final_verdict']
    assert execution_replay_payload['session_primary_digests']['runtime_contract']
    assert execution_replay_payload['session_primary_contract_hints']['migration_status'] == 'compatibility-layer-active'
    assert execution_replay_payload['session_legacy_contract_layer']['legacy_verdict_count'] > 0
    assert 'next_run_status' in execution_replay_payload
    assert execution_replay_payload['replay_results']
    assert execution_replay_payload['transition_preview']
    assert execution_replay_payload['checkpoint_preview']
    assert 'recovery_owner' in execution_replay_payload['next_recovery_cursor']
    execution_replay_text = execution_replay_md.read_text(encoding='utf-8')
    assert '# Writer Imitation Execution Replay Preview' in execution_replay_text
    assert 'primary_operator_entrypoint: writer-imitate-operator-surface.md' in execution_replay_text
    assert 'legacy_operator_entrypoint: writer-imitate-legacy-contract-surface.md' in execution_replay_text
    assert '## Primary Verdicts' in execution_replay_text
    assert '## Primary Digests' in execution_replay_text
    assert execution_replay_text.index('## Primary Verdicts') < execution_replay_text.index('## Operator-Facing Stable Contract')
    assert '## Operator-Facing Stable Contract' in execution_replay_text
    assert '## Primary Contract Migration Hints' in execution_replay_text
    assert '## Replay Results' in execution_replay_text
    assert '## Transition Preview' in execution_replay_text
    assert '## Checkpoint Preview' in execution_replay_text
    assert '## Next Recovery Cursor' in execution_replay_text

    result = runner.invoke(
        app,
        ['writer-imitate-apply-replay', '--output-dir', str(output_dir)],
    )
    assert result.exit_code == 0
    assert execution_apply_json.exists()
    assert execution_apply_md.exists()
    execution_apply_payload = json.loads(execution_apply_json.read_text(encoding='utf-8'))
    assert execution_apply_payload['contract_version'] == 'writer-imitate-execution-apply.v1'
    assert execution_apply_payload['primary_operator_entrypoint'] == 'writer-imitate-operator-surface.json'
    assert execution_apply_payload['legacy_operator_entrypoint'] == 'writer-imitate-legacy-contract-surface.json'
    assert execution_apply_payload['session_operator_contract']['owners']['session_recovery_owner']
    assert execution_apply_payload['session_primary_verdicts']['promotion_verdict']
    assert execution_apply_payload['session_primary_digests']['operating_digest']
    assert execution_apply_payload['session_primary_contract_hints']['preferred_verdict_source'] == 'session_primary_verdicts'
    assert execution_apply_payload['session_legacy_contract_layer']['legacy_digest_count'] > 0
    assert 'apply_status' in execution_apply_payload
    assert 'next_resume_hint' in execution_apply_payload
    execution_apply_text = execution_apply_md.read_text(encoding='utf-8')
    assert '# Writer Imitation Execution Apply Preview' in execution_apply_text
    assert 'primary_operator_entrypoint: writer-imitate-operator-surface.md' in execution_apply_text
    assert 'legacy_operator_entrypoint: writer-imitate-legacy-contract-surface.md' in execution_apply_text
    assert '## Primary Verdicts' in execution_apply_text
    assert '## Primary Digests' in execution_apply_text
    assert execution_apply_text.index('## Primary Verdicts') < execution_apply_text.index('## Operator-Facing Stable Contract')
    assert '## Operator-Facing Stable Contract' in execution_apply_text
    assert '## Primary Contract Migration Hints' in execution_apply_text
    assert '## Applied Tickets' in execution_apply_text
    assert '## Applied Transitions' in execution_apply_text
    assert '## Applied Checkpoints' in execution_apply_text

    result = runner.invoke(
        app,
        ['writer-imitate-live-control-state', '--output-dir', str(output_dir)],
    )
    assert result.exit_code == 0
    assert live_control_state_json.exists()
    assert live_control_state_md.exists()
    live_control_state_payload = json.loads(live_control_state_json.read_text(encoding='utf-8'))
    assert live_control_state_payload['contract_version'] == 'writer-imitate-live-control-state.v1'
    assert live_control_state_payload['live_state_status'] == 'preview-backed-pending-live-mutation'
    assert live_control_state_payload['pending_checkpoint_writeback']
    assert live_control_state_payload['live_mutation_readiness']['status'] == 'not-ready'
    assert live_control_state_payload['live_mutation_plan']['execution_order']
    assert live_control_state_payload['live_mutation_pilot_wave']['wave_id'] == 'live-mutation-wave-01'
    live_control_state_text = live_control_state_md.read_text(encoding='utf-8')
    assert '# Writer Imitation Live Control State' in live_control_state_text
    assert '## Live Mutation Readiness' in live_control_state_text
    assert '## Live Mutation Plan' in live_control_state_text
    assert '## Live Mutation Pilot Wave' in live_control_state_text
    assert '## Pending Checkpoint Writeback' in live_control_state_text
    assert '## Pending Transition Apply' in live_control_state_text

    result = runner.invoke(
        app,
        ['writer-imitate-live-mutation-preview', '--output-dir', str(output_dir)],
    )
    assert result.exit_code == 0
    assert live_mutation_preview_json.exists()
    assert live_mutation_preview_md.exists()
    live_mutation_preview_payload = json.loads(live_mutation_preview_json.read_text(encoding='utf-8'))
    assert live_mutation_preview_payload['contract_version'] == 'writer-imitate-live-mutation-preview.v1'
    assert live_mutation_preview_payload['live_mutation_pilot_wave']['wave_id'] == 'live-mutation-wave-01'
    live_mutation_preview_text = live_mutation_preview_md.read_text(encoding='utf-8')
    assert '# Writer Imitation Live Mutation Preview' in live_mutation_preview_text
    assert '## Live Mutation Readiness' in live_mutation_preview_text
    assert '## Live Mutation Plan' in live_mutation_preview_text
    assert '## Live Mutation Pilot Wave' in live_mutation_preview_text
    assert '## Checkpoint Writeback Preview' in live_mutation_preview_text
    assert '## Transition Apply Preview' in live_mutation_preview_text

    result = runner.invoke(
        app,
        ['writer-imitate-apply-live-checkpoint', '--output-dir', str(output_dir)],
    )
    assert result.exit_code == 0
    assert live_checkpoint_state_json.exists()
    assert live_checkpoint_state_md.exists()
    live_checkpoint_state_payload = json.loads(live_checkpoint_state_json.read_text(encoding='utf-8'))
    assert live_checkpoint_state_payload['contract_version'] == 'writer-imitate-live-checkpoint-state.v1'
    assert live_checkpoint_state_payload['live_checkpoint_status'] == 'checkpoint-writeback-applied-local'
    assert live_checkpoint_state_payload['applied_checkpoints']
    live_checkpoint_state_text = live_checkpoint_state_md.read_text(encoding='utf-8')
    assert '# Writer Imitation Live Checkpoint State' in live_checkpoint_state_text
    assert '## Applied Checkpoints' in live_checkpoint_state_text

    result = runner.invoke(
        app,
        ['writer-imitate-apply-live-transition', '--output-dir', str(output_dir)],
    )
    assert result.exit_code == 0
    assert live_transition_state_json.exists()
    assert live_transition_state_md.exists()
    live_transition_state_payload = json.loads(live_transition_state_json.read_text(encoding='utf-8'))
    assert live_transition_state_payload['contract_version'] == 'writer-imitate-live-transition-state.v1'
    assert live_transition_state_payload['live_transition_status'] == 'transition-apply-applied-local'
    assert live_transition_state_payload['applied_transitions']
    live_transition_state_text = live_transition_state_md.read_text(encoding='utf-8')
    assert '# Writer Imitation Live Transition State' in live_transition_state_text
    assert '## Applied Transitions' in live_transition_state_text

    result = runner.invoke(
        app,
        ['writer-imitate-validate-live-state', '--output-dir', str(output_dir)],
    )
    assert result.exit_code == 0
    assert live_validation_state_json.exists()
    assert live_validation_state_md.exists()
    live_validation_state_payload = json.loads(live_validation_state_json.read_text(encoding='utf-8'))
    assert live_validation_state_payload['contract_version'] == 'writer-imitate-live-validation-state.v1'
    assert live_validation_state_payload['live_validation_status'] == 'validated-local'
    assert live_validation_state_payload['validation_checks']
    live_validation_state_text = live_validation_state_md.read_text(encoding='utf-8')
    assert '# Writer Imitation Live Validation State' in live_validation_state_text
    assert '## Validation Checks' in live_validation_state_text

    result = runner.invoke(
        app,
        ['writer-imitate-resume-replay', '--output-dir', str(output_dir)],
    )
    assert result.exit_code == 0
    assert execution_resume_json.exists()
    assert execution_resume_md.exists()
    execution_resume_payload = json.loads(execution_resume_json.read_text(encoding='utf-8'))
    assert execution_resume_payload['contract_version'] == 'writer-imitate-execution-resume.v1'
    assert execution_resume_payload['primary_operator_entrypoint'] == 'writer-imitate-operator-surface.json'
    assert execution_resume_payload['legacy_operator_entrypoint'] == 'writer-imitate-legacy-contract-surface.json'
    assert execution_resume_payload['session_operator_contract']['status']['session_lane_status']
    assert execution_resume_payload['session_primary_verdicts']['runtime_verdict']
    assert execution_resume_payload['session_primary_digests']['control_summary']
    assert execution_resume_payload['session_primary_contract_hints']['preferred_digest_source'] == 'session_primary_digests'
    assert execution_resume_payload['session_legacy_contract_layer']['status'] == 'compatibility-layer-active'
    assert 'resume_status' in execution_resume_payload
    assert execution_resume_payload['resume_steps']
    execution_resume_text = execution_resume_md.read_text(encoding='utf-8')
    assert '# Writer Imitation Execution Resume Plan' in execution_resume_text
    assert 'primary_operator_entrypoint: writer-imitate-operator-surface.md' in execution_resume_text
    assert 'legacy_operator_entrypoint: writer-imitate-legacy-contract-surface.md' in execution_resume_text
    assert '## Primary Verdicts' in execution_resume_text
    assert '## Primary Digests' in execution_resume_text
    assert execution_resume_text.index('## Primary Verdicts') < execution_resume_text.index('## Operator-Facing Stable Contract')
    assert '## Operator-Facing Stable Contract' in execution_resume_text
    assert '## Primary Contract Migration Hints' in execution_resume_text
    assert '## Resume Targets' in execution_resume_text
    assert '## Resume Steps' in execution_resume_text


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
