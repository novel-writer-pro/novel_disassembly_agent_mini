from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novel_analyzer.reporting.branch_report import render_branch_report
from novel_analyzer.services.export_service import ExportService
from novel_analyzer.services.fact_service import FactService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.retrieval_service import RetrievalService
from novel_analyzer.services.risk_audit_service import RiskAuditService
from novel_analyzer.services.run_service import RunService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    from novel_analyzer.database.session import create_schema
    create_schema(engine)
    return Session(engine)


def test_render_branch_report_contains_status_and_windows(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        retrieval = RetrievalService(session)
        facts = FactService(session)
        graph = GraphService(session)
        for idx in range(1, 6):
            artifact = RunService(session).record_chapter_artifact(
                branch.id,
                idx,
                {
                    'chapter_index': idx,
                    'normalized_title': f'第{idx}章',
                    'chapter_summary': f'第{idx}章摘要',
                    'key_entities': ['卫图', '养生功'],
                    'key_events': [f'第{idx}章事件'],
                    'continuity_notes': [f'第{idx}章衔接'],
                    'writer_learning_notes': [],
                    'ooc_candidates': (
                        [
                            {
                                'character_name': '卫图',
                                'risk_type': 'motivation_shift',
                                'severity': 'low',
                                'summary': '卫图在首章存在轻微动机偏移候选。',
                                'supporting_evidence': ['第1章事件'],
                                'counter_evidence': ['也可能是首章信息尚未展开完全'],
                            }
                        ]
                        if idx == 1
                        else []
                    ),
                    'unsupported_inferences': [],
                    'ambiguous_points': [],
                    'needs_human_review': idx == 1,
                    'quality_gate_notes': [],
                    'hook_score': 4.5,
                    'dimensions': [],
                    'state_transition_notes': [f'第{idx}章推进'],
                    'evidence_backed_resolutions': [f'第{idx}章解决'],
                    'unresolved_threads': [f'第{idx}章未解'],
                },
            )
            retrieval.materialize_for_artifact(artifact.id)
            facts.materialize_for_artifact(artifact.id)
            graph.materialize_for_artifact(artifact.id)
            facts.materialize_window_if_ready(branch.id, idx, 5)
            if idx == 1:
                RiskAuditService(session).generate_for_chapter(branch.id, idx)
        bundle = ExportService(session).export_branch_bundle(run.id, branch.id)
        report = render_branch_report(bundle)
        assert '# Branch Report' in report
        assert '## Status' in report
        assert '## Audit Conclusion' in report
        assert 'Content Judgement' in report
        assert 'Risk Judgement' in report
        assert 'Blocking Judgement' in report
        assert 'Recommended Action' in report
        assert '## Failed Summary' in report
        assert '## Risk Summary' in report
        assert '## Review Summary' in report
        assert '### Human Review Candidates' in report
        assert '### Review Candidate Evidence Preview' in report
        assert '### Review Candidate Clusters' in report
        assert '### Phase-2 Risk Highlights' not in report
        assert 'title=' in report
        assert 'action:' in report
        assert 'priority=' in report
        assert 'status=' in report
        assert '待复核' in report
        assert 'pattern=' in report
        assert 'span=' in report
        assert 'review_candidate_count' in report
        assert 'confidence=' in report
        assert 'checkers=' in report
        assert 'types=' in report
        assert 'continuity:' in report
        assert 'branch-signal:' in report
        assert '## Windows' in report
        assert '## Graph Overview' in report
        assert '## State Summary' in report
        assert '## Chapter Output Summary' in report
        assert '## Reasoning Graph' in report
        assert '### Reasoning Paths' in report


def test_render_branch_report_highlights_phase2_risk_clusters(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        artifact = RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '恢复窗口测试',
                'chapter_summary': '本章恢复时长存在可疑压缩。',
                'key_entities': ['卫图'],
                'key_events': ['卫图三日后回城又当夜再战'],
                'continuity_notes': ['主线推进。'],
                'timeline_signals': ['三日后回城', '当夜再次出手'],
                'unsupported_inferences': ['“当夜已完成全部恢复”缺少直接证据支撑'],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'dimensions': [],
            },
        )
        RetrievalService(session).materialize_for_artifact(artifact.id)
        FactService(session).materialize_for_artifact(artifact.id)
        GraphService(session).materialize_for_artifact(artifact.id)
        RiskAuditService(session).generate_for_chapter(branch.id, 1)
        bundle = ExportService(session).export_branch_bundle(run.id, branch.id)
        report = render_branch_report(bundle)
        assert '### Phase-2 Risk Highlights' in report
        assert '恢复窗口不足候选簇' in report
        assert 'focus:' in report
        assert 'phase2_focus_top:' in report
        assert 'by_phase2_focus:' in report


def test_render_branch_report_includes_manual_review_metadata(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        artifact = RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '命格初现',
                'chapter_summary': '卫图觉醒命格。',
                'key_entities': ['卫图'],
                'key_events': ['卫图觉醒命格'],
                'continuity_notes': ['主线推进。'],
                'ooc_candidates': [
                    {
                        'character_name': '卫图',
                        'risk_type': 'motivation_shift',
                        'severity': 'low',
                        'summary': '卫图存在轻微动机偏移。',
                        'supporting_evidence': ['第1章事件'],
                        'counter_evidence': ['也可能是信息尚未展开完全'],
                    }
                ],
                'needs_human_review': True,
                'dimensions': [],
            },
        )
        RetrievalService(session).materialize_for_artifact(artifact.id)
        FactService(session).materialize_for_artifact(artifact.id)
        GraphService(session).materialize_for_artifact(artifact.id)
        RiskAuditService(session).generate_for_chapter(branch.id, 1)
        bundle = ExportService(session).export_branch_bundle(run.id, branch.id)
        cluster = bundle['risk_summary']['review_candidate_clusters'][0]
        cluster['cluster_status'] = 'resolved'
        cluster['review_owner'] = 'editor-a'
        cluster['resolved_at'] = '2026-04-29T02:00:00Z'
        cluster['review_result'] = 'confirmed-benign'
        cluster['review_result_label'] = '确认无问题'
        cluster['review_notes'] = '已人工确认该问题无需升级。'
        cluster['review_history_count'] = 2
        cluster['workflow_lane'] = 'resolved_queue'
        cluster['queue_priority'] = 'done'
        cluster['action_required'] = False
        cluster['suggested_deadline_level'] = 'none'
        cluster['batch_operation_hint'] = 'batch_close_ready_candidates'
        cluster['auto_next_action'] = '保留人物连续性复核簇的审计记录，并继续关注后续章节是否复发。'
        cluster['latest_review_event'] = {
            'previous_cluster_status': 'needs_review',
            'cluster_status': 'resolved',
            'review_result': 'confirmed-benign',
            'review_owner': 'editor-a',
            'review_actor': 'review-bot',
            'created_at': '2026-04-29T02:05:00Z',
        }
        bundle['audit_conclusion']['review_progress_note'] = '已人工处理问题簇 1 个。'
        bundle['audit_conclusion']['resolved_cluster_note'] = '当前已有 1 个问题簇被标记为 resolved。'
        bundle['audit_conclusion']['review_result_note'] = '已确认无问题 1 个。'
        bundle['audit_conclusion']['review_storage_note'] = '当前 review 数据来自数据库主路径。'
        bundle['audit_conclusion']['review_owner_note'] = '当前已记录复核人中，editor-a 处理了 1 个问题簇。'
        bundle['audit_conclusion']['current_owner_note'] = '当前问题簇负责人分布中，editor-a 负责 1 个问题簇。'
        bundle['audit_conclusion']['review_actor_note'] = '最近审查动作记录中，review-bot 执行了 1 次变更。'
        bundle['audit_conclusion']['latest_event_type_note'] = '最近一批问题簇的最新动作类型中，assignment_update 出现了 1 次。'
        bundle['audit_conclusion']['pending_assignment_note'] = '存在 1 个已交接但未闭环的问题簇；优先关注 人物连续性复核簇（owner=editor-a）。'
        bundle['audit_conclusion']['latest_review_note'] = '最近一次复核记录：状态=resolved，结果=confirmed-benign，处理人=editor-a，操作人=review-bot。'
        report = render_branch_report(bundle)
        assert 'owner: editor-a' in report
        assert 'resolved_at: 2026-04-29T02:00:00Z' in report
        assert 'result: confirmed-benign (确认无问题)' in report
        assert 'notes: 已人工确认该问题无需升级。' in report
        assert 'workflow_lane: resolved_queue' in report
        assert 'queue_priority: done' in report
        assert 'action_required: False' in report
        assert 'suggested_deadline_level: none' in report
        assert 'batch_operation_hint: batch_close_ready_candidates' in report
        assert 'auto_next_action:' in report
        assert 'history_count: 2' in report
        assert 'latest_event: from=needs_review->resolved | result=confirmed-benign | owner=editor-a | actor=review-bot | created_at=2026-04-29T02:05:00Z' in report
        assert 'Review Progress: 已人工处理问题簇 1 个。' in report
        assert 'Resolved Clusters: 当前已有 1 个问题簇被标记为 resolved。' in report
        assert 'Review Result: 已确认无问题 1 个。' in report
        assert 'Review Storage: 当前 review 数据来自数据库主路径。' in report
        assert 'Review Owner: 当前已记录复核人中，editor-a 处理了 1 个问题簇。' in report
        assert 'Current Owner: 当前问题簇负责人分布中，editor-a 负责 1 个问题簇。' in report
        assert 'Review Actor: 最近审查动作记录中，review-bot 执行了 1 次变更。' in report
        assert 'Latest Event Type: 最近一批问题簇的最新动作类型中，assignment_update 出现了 1 次。' in report
        assert 'Pending Assignment: 存在 1 个已交接但未闭环的问题簇；优先关注 人物连续性复核簇（owner=editor-a）。' in report
        assert 'Latest Review: 最近一次复核记录：状态=resolved，结果=confirmed-benign，处理人=editor-a，操作人=review-bot。' in report
        assert '## Review Summary' in report
        assert 'current_owner_top:' in report
        assert 'workflow_lane_top:' in report
        assert 'queue_priority_top:' in report
        assert 'deadline_level_top:' in report
        assert 'batch_operation_hint_top:' in report
        assert 'batch_suggestions:' in report
        assert 'auto_next_action_code_top:' in report
        assert 'auto_next_action_top:' in report
        assert 'escalation_reason_code_top:' in report
        assert 'ordering_strategy' in report
        assert 'action_bucket' in report
        assert 'batch_priority' in report
        assert 'status=resolved (已关闭)' in report
