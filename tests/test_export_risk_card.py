from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novel_analyzer.database.session import create_schema
from novel_analyzer.runtime.cluster_review_state import write_cluster_review_state
from novel_analyzer.services.cluster_review_service import ClusterReviewService
from novel_analyzer.services.export_service import ExportService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.risk_audit_service import RiskAuditService
from novel_analyzer.services.run_service import RunService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def test_export_chapter_bundle_includes_risk_card(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '命格初现',
                'chapter_summary': '卫图在本章做出异常决定。',
                'key_entities': ['卫图'],
                'key_events': ['卫图做出异常决定'],
                'continuity_notes': ['主线推进。'],
                'ooc_candidates': [
                    {
                        'character_name': '卫图',
                        'risk_type': 'motivation_shift',
                        'severity': 'medium',
                        'summary': '卫图目标改变过快。',
                        'supporting_evidence': ['前文目标A'],
                        'counter_evidence': ['也许有新情报'],
                    }
                ],
                'unsupported_inferences': [],
                'ambiguous_points': [],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'hook_score': 4.0,
                'dimensions': [],
            },
        )
        RiskAuditService(session).generate_for_chapter(branch.id, 1)
        bundle = ExportService(session).export_chapter_bundle(branch.id, 1)
        assert bundle['risk_card'] is not None
        assert bundle['risk_card']['top_risks'][0]['checker_name'] == 'character_ooc'

        branch_bundle = ExportService(session).export_branch_bundle(run.id, branch.id)
        assert branch_bundle['review_storage_mode'] in {'db', 'file-fallback'}
        assert branch_bundle['risk_summary']['risk_card_count'] == 1
        assert branch_bundle['risk_summary']['checker_result_count'] == 5
        assert branch_bundle['risk_summary']['review_candidate_count'] == 1
        assert branch_bundle['audit_conclusion']
        assert branch_bundle['audit_conclusion']['content_judgement']
        assert branch_bundle['audit_conclusion']['risk_judgement']
        assert branch_bundle['audit_conclusion']['blocking_judgement']
        assert branch_bundle['audit_conclusion']['recommended_action']
        assert branch_bundle['risk_summary']['review_candidates_summary']
        assert branch_bundle['risk_summary']['review_candidate_clusters']
        candidate = branch_bundle['risk_summary']['review_candidates_summary'][0]
        assert 'checker_names' in candidate
        assert 'risk_types' in candidate
        assert 'continuity_evidence_preview' in candidate
        assert 'branch_signal_preview' in candidate
        cluster = branch_bundle['risk_summary']['review_candidate_clusters'][0]
        assert 'cluster_title' in cluster
        assert 'suggested_review_action' in cluster
        assert cluster['review_priority'] in {'P1', 'P2', 'P3'}
        assert cluster['cluster_status'] in {'open', 'needs_review', 'reviewed', 'escalated', 'reopened', 'resolved'}
        assert cluster['pattern_label'] in {'单点问题', '集中爆发型问题', '持续型问题'}
        assert 'chapters' in cluster
        assert 'chapter_span' in cluster
        assert 'chapter_count' in cluster
        assert branch_bundle['failed_summary'] == []


def test_branch_snapshot_rows_include_risk_level_and_count(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '命格初现',
                'chapter_summary': '卫图在本章做出异常决定。',
                'key_entities': ['卫图'],
                'key_events': ['卫图做出异常决定'],
                'continuity_notes': ['主线推进。'],
                'ooc_candidates': [
                    {
                        'character_name': '卫图',
                        'risk_type': 'motivation_shift',
                        'severity': 'medium',
                        'summary': '卫图目标改变过快。',
                        'supporting_evidence': ['前文目标A'],
                        'counter_evidence': ['也许有新情报'],
                    }
                ],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'dimensions': [],
            },
        )
        RiskAuditService(session).generate_for_chapter(branch.id, 1)
        row = ExportService(session).chapter_index_service.list_rows(branch.id)[0]
        assert row.risk_level in {'medium', 'high', 'low'}
        assert row.risk_count >= 1


def test_review_candidate_prefers_more_specific_cross_checker_signal(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '跨 checker 候选排序测试',
                'chapter_summary': '本章存在人物与规则双重可疑点。',
                'key_entities': ['卫图'],
                'key_events': ['卫图突然突破限制'],
                'continuity_notes': ['主线推进。'],
                'ambiguous_points': ['人物态度变化存在歧义。'],
                'needs_human_review': True,
                'world_rule_issues': [
                    {
                        'risk_type': 'rule_consistency',
                        'severity': 'medium',
                        'summary': '本章对规则限制的突破缺少明确解释。',
                        'supporting_evidence': ['命格限制突然被绕过'],
                        'counter_evidence': ['也可能是特殊条件触发'],
                    }
                ],
                'dimensions': [],
            },
        )
        RiskAuditService(session).generate_for_chapter(branch.id, 1)
        branch_bundle = ExportService(session).export_branch_bundle(run.id, branch.id)
        candidate = branch_bundle['risk_summary']['review_candidates_summary'][0]
        assert 'world_rule_consistency' in candidate['checker_names']
        assert candidate['summary'] == '本章对规则限制的突破缺少明确解释。'
        assert 'rule_consistency' in candidate['risk_types']
        cluster = branch_bundle['risk_summary']['review_candidate_clusters'][0]
        assert '规则' in cluster['cluster_title']
        assert 'human_review_candidate' not in candidate['risk_types']
        assert 'rule_consistency' in cluster['risk_types']
        assert cluster['sample_summary'] == '本章对规则限制的突破缺少明确解释。'


def test_build_audit_conclusion_uses_failed_and_candidate_signals() -> None:
    conclusion = ExportService._build_audit_conclusion(
        completed_chapters=103,
        manifest_chapter_count=775,
        failed_summary=[{'chapter_index': 104}],
        high_risk_chapters=[],
        review_candidate_count=4,
    )
    assert '阶段性审查结果' in conclusion['content_judgement']
    assert '执行阻塞' in conclusion['blocking_judgement']
    assert '失败章节' in conclusion['recommended_action']


def test_build_audit_conclusion_uses_dense_candidate_threshold() -> None:
    conclusion = ExportService._build_audit_conclusion(
        completed_chapters=120,
        manifest_chapter_count=150,
        failed_summary=[],
        high_risk_chapters=[],
        review_candidate_count=6,
    )
    assert '候选风险分布较密集' in conclusion['content_judgement']
    assert '人工复核候选较多' in conclusion['risk_judgement']


def test_derive_cluster_status_prefers_needs_review_for_dense_or_high_confidence_clusters() -> None:
    assert ExportService._derive_cluster_status(chapter_count=5, max_confidence=0.2, review_priority_value='P3') == 'needs_review'
    assert ExportService._derive_cluster_status(chapter_count=1, max_confidence=0.7, review_priority_value='P3') == 'needs_review'
    assert ExportService._derive_cluster_status(chapter_count=1, max_confidence=0.2, review_priority_value='P1') == 'needs_review'
    assert ExportService._derive_cluster_status(chapter_count=1, max_confidence=0.2, review_priority_value='P3') == 'open'


def test_cluster_review_candidates_prefers_sustained_and_more_specific_items_first() -> None:
    clusters = ExportService._cluster_review_candidates(
        [
            {
                'chapter_index': 10,
                'checker_names': ['character_ooc'],
                'risk_types': ['human_review_candidate'],
                'confidence': 0.35,
                'summary': '泛化候选',
                'title': '第10章',
            },
            {
                'chapter_index': 14,
                'checker_names': ['character_ooc'],
                'risk_types': ['relationship_shift_candidate'],
                'confidence': 0.35,
                'summary': '关系漂移',
                'title': '第14章',
            },
            {
                'chapter_index': 30,
                'checker_names': ['world_rule_consistency'],
                'risk_types': ['rule_support_gap'],
                'confidence': 0.6,
                'summary': '规则支撑缺口',
                'title': '第30章',
            },
        ]
    )
    assert clusters
    assert clusters[0]['cluster_title'] in {'人物风险簇：relationship_shift_candidate', '规则风险簇：rule_support_gap'}


def test_export_branch_bundle_applies_manual_cluster_status_override(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '命格初现',
                'chapter_summary': '卫图在本章做出异常决定。',
                'key_entities': ['卫图'],
                'key_events': ['卫图做出异常决定'],
                'continuity_notes': ['主线推进。'],
                'ooc_candidates': [
                    {
                        'character_name': '卫图',
                        'risk_type': 'motivation_shift',
                        'severity': 'medium',
                        'summary': '卫图目标改变过快。',
                        'supporting_evidence': ['前文目标A'],
                        'counter_evidence': ['也许有新情报'],
                    }
                ],
                'needs_human_review': True,
                'dimensions': [],
            },
        )
        RiskAuditService(session).generate_for_chapter(branch.id, 1)
        bundle = ExportService(session).export_branch_bundle(run.id, branch.id)
        cluster = bundle['risk_summary']['review_candidate_clusters'][0]
        ClusterReviewService(session).write(
            branch_id=branch.id,
            cluster_key=cluster['cluster_key'],
            cluster_status='resolved',
            review_notes='已人工复核',
            review_result='confirmed-benign',
        )
        overridden = ExportService(session).export_branch_bundle(run.id, branch.id)
        cluster2 = overridden['risk_summary']['review_candidate_clusters'][0]
        assert cluster2['cluster_status'] == 'resolved'
        assert cluster2['review_notes'] == '已人工复核'


def test_export_branch_bundle_applies_manual_cluster_metadata_override(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '命格初现',
                'chapter_summary': '卫图在本章做出异常决定。',
                'key_entities': ['卫图'],
                'key_events': ['卫图做出异常决定'],
                'continuity_notes': ['主线推进。'],
                'ooc_candidates': [
                    {
                        'character_name': '卫图',
                        'risk_type': 'motivation_shift',
                        'severity': 'medium',
                        'summary': '卫图目标改变过快。',
                        'supporting_evidence': ['前文目标A'],
                        'counter_evidence': ['也许有新情报'],
                    }
                ],
                'needs_human_review': True,
                'dimensions': [],
            },
        )
        RiskAuditService(session).generate_for_chapter(branch.id, 1)
        bundle = ExportService(session).export_branch_bundle(run.id, branch.id)
        cluster = bundle['risk_summary']['review_candidate_clusters'][0]
        ClusterReviewService(session).write(
            branch_id=branch.id,
            cluster_key=cluster['cluster_key'],
            cluster_status='resolved',
            review_notes='已复核并确认无问题',
            review_owner='editor-a',
            resolved_at='2026-04-29T02:00:00Z',
            review_result='confirmed-benign',
        )
        overridden = ExportService(session).export_branch_bundle(run.id, branch.id)
        cluster2 = overridden['risk_summary']['review_candidate_clusters'][0]
        assert cluster2['review_owner'] == 'editor-a'
        assert cluster2['resolved_at'] == '2026-04-29T02:00:00Z'
        assert cluster2['review_result'] == 'confirmed-benign'
        assert cluster2['review_result_label'] == '确认无问题'
        assert cluster2['review_history_count'] >= 1
        assert isinstance(cluster2['review_history'], list)
        assert cluster2['latest_review_event']['review_owner'] == 'editor-a'
        assert cluster2['latest_review_event']['created_at']
        assert 'review_progress_note' in overridden['audit_conclusion']
        assert 'review_result_note' in overridden['audit_conclusion']
        assert 'review_storage_note' in overridden['audit_conclusion']
        assert 'review_owner_note' in overridden['audit_conclusion']
        assert 'latest_review_note' in overridden['audit_conclusion']
        assert '未见需继续升级的明确风险' in overridden['audit_conclusion']['risk_judgement']


def test_write_cluster_review_state_rejects_unknown_review_result(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_cluster_review_state(
            'branch-x',
            'cluster-y',
            'resolved',
            review_result='custom-free-text',
        )


def test_write_cluster_review_state_requires_review_result_when_resolved(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_cluster_review_state(
            'branch-x',
            'cluster-y',
            'resolved',
            review_result='',
        )


def test_write_cluster_review_state_requires_notes_for_needs_escalation(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_cluster_review_state(
            'branch-x',
            'cluster-y',
            'needs_review',
            review_result='needs-escalation',
            review_notes='',
        )


def test_write_cluster_review_state_requires_matching_status_for_needs_escalation(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_cluster_review_state(
            'branch-x',
            'cluster-y',
            'resolved',
            review_result='needs-escalation',
            review_notes='需要升级',
        )


def test_cluster_review_service_persists_review_record_in_database(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        service = ClusterReviewService(session)
        service.write(
            branch_id=branch.id,
            cluster_key='character_ooc|::|human_review_candidate',
            cluster_status='reviewed',
            review_result='confirmed-benign',
            review_notes='已读',
            review_owner='editor-a',
            resolved_at='2026-04-29T02:00:00Z',
        )
        payload = service.read_branch(branch.id)
        assert payload['character_ooc|::|human_review_candidate']['cluster_status'] == 'reviewed'
        assert payload['character_ooc|::|human_review_candidate']['review_owner'] == 'editor-a'
        history = service.read_history(branch.id, 'character_ooc|::|human_review_candidate')
        assert len(history) == 1
        assert history[0]['previous_cluster_status'] == ''
        assert history[0]['cluster_status'] == 'reviewed'
