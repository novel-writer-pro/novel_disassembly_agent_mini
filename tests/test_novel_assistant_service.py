from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novel_analyzer.database.session import create_schema
from novel_analyzer.services.fact_service import FactService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.novel_assistant_service import NovelAssistantService
from novel_analyzer.services.run_service import RunService
from novel_analyzer.services.retrieval_service import RetrievalService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def test_novel_assistant_service_builds_branch_assistant_pack(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        fact_service = FactService(session)
        graph_service = GraphService(session)
        retrieval_service = RetrievalService(session)
        for idx, title, summary, entities in [
            (1, '命格初现', '卫图觉醒命格', ['卫图', '命格']),
            (2, '资源铺垫', '二姑帮卫图筹措资源', ['二姑', '卫图']),
        ]:
            artifact = RunService(session).record_chapter_artifact(
                branch.id,
                idx,
                {
                    'chapter_index': idx,
                    'normalized_title': title,
                    'chapter_summary': summary,
                    'key_entities': entities,
                    'key_events': [summary],
                    'continuity_notes': [f'第{idx}章承接'],
                    'writer_learning_notes': [],
                    'unsupported_inferences': [],
                    'ambiguous_points': [],
                    'needs_human_review': False,
                    'quality_gate_notes': [],
                    'hook_score': 4.0,
                    'dimensions': [],
                },
            )
            fact_service.materialize_for_artifact(artifact.id)
            graph_service.materialize_for_artifact(artifact.id)
            retrieval_service.materialize_for_artifact(artifact.id)

        pack = NovelAssistantService(session).build_branch_assistant_pack(
            branch.id,
            query='卫图',
            from_chapter_index=1,
            upto_chapter_index=2,
            focus_label='卫图',
        )
        assert pack['contract_version'] == 'novel-assistant.v1'
        assert pack['assistant_summary']['chapter_count'] == 2
        assert 'retrieve_evidence' in pack['supported_actions']
        assert 'continue_writing_preparation' in pack['supported_actions']
        assert 'imitation_preparation' in pack['supported_actions']
        assert pack['author_knowledge']['focus_label'] == '卫图'
        assert pack['whole_book_readiness_summary']
        assert pack['sample_evidence_summary']
        assert pack['whole_book_consistency_backflow_pack']['contract_version'] == 'whole-book-consistency-backflow-pack.v1'
        assert pack['whole_book_consistency_backflow_pack']['release_impact']
        assert pack['retrieval_benchmark_summary']['contract_version'] == 'retrieval-benchmark-summary.v1'
        if pack['retrieval_benchmark_summary'].get('degraded'):
            assert pack['retrieval_benchmark_summary']['reason']
        else:
            assert pack['retrieval_benchmark_summary']['query_count'] >= 1
        assert pack['preparation_guidance']['next_chapter_preparation']
        assert pack['preparation_guidance']['imitation_preparation']
        assert pack['preparation_guidance']['risk_gate_preflight']
        assert pack['continuation_pack'] is not None
        assert pack['imitation_pack'] is not None
        assert pack['original_planning_pack']['contract_version'] == 'original-planning-pack.v1'
        assert pack['creation_control_pack']['contract_version'] == 'creation-control-pack.v1'
        assert pack['editor_revision_pack']['contract_version'] == 'editor-revision-pack.v1'
        assert pack['reader_feedback_pack']['contract_version'] == 'reader-feedback-pack.v1'
        assert 'feedback_summary' in pack['reader_feedback_pack']
        assert pack['feedback_revision_bridge_pack']['contract_version'] == 'feedback-revision-bridge-pack.v1'
        assert pack['feedback_revision_bridge_pack']['bridge_actions']
        assert pack['chapter_draft_preparation_pack']['contract_version'] == 'chapter-draft-preparation-pack.v1'
        assert pack['chapter_draft_preparation_pack']['scene_outline']
        assert pack['direct_draft_skeleton_pack']['contract_version'] == 'direct-draft-skeleton-pack.v1'
        assert pack['direct_draft_skeleton_pack']['scene_blocks']
        assert pack['direct_draft_skeleton_pack']['draft_text']
        assert pack['direct_revision_loop_pack']['contract_version'] == 'direct-revision-loop-pack.v1'
        assert pack['direct_revision_loop_pack']['revised_blocks']
        assert pack['direct_revision_loop_pack']['revision_text']
        assert pack['automatic_rewrite_guidance_pack']['contract_version'] == 'automatic-rewrite-guidance-pack.v1'
        assert pack['automatic_rewrite_guidance_pack']['rewrite_steps']
        assert pack['automatic_rewrite_guidance_pack']['guidance_text']
        assert pack['automatic_rewrite_guidance_pack']['feedback_bridge_actions']
        assert 'feedback_signals' in pack['automatic_prose_rewrite_pack']
        assert pack['automatic_prose_rewrite_pack']['contract_version'] == 'automatic-prose-rewrite-pack.v1'
        assert pack['automatic_prose_rewrite_pack']['rewritten_blocks']
        assert pack['automatic_prose_rewrite_pack']['rewrite_text']
        assert pack['final_draft_candidate_pack']['contract_version'] == 'final-draft-candidate-pack.v1'
        assert pack['final_draft_candidate_pack']['candidate_blocks']
        assert pack['final_draft_candidate_pack']['candidate_text']
        assert 'negative_feedback_signal_count' in pack['final_draft_candidate_pack']['review_gate']
        assert 'reader_feedback_signals' in pack['final_draft_candidate_pack']
        assert pack['publish_ready_release_pack']['contract_version'] == 'publish-ready-release-pack.v1'
        assert 'release_gate' in pack['publish_ready_release_pack']
        assert 'whole_book_consistency_ready' in pack['publish_ready_release_pack']['release_gate']
        assert pack['publish_ready_release_pack']['release_summary']
        assert pack['sample_based_release_criteria_bundle']['contract_version'] == 'sample-based-release-criteria-bundle.v1'
        assert 'criteria' in pack['sample_based_release_criteria_bundle']
        assert 'reader_feedback_ready' in pack['sample_based_release_criteria_bundle']['criteria']
        assert pack['sample_based_release_criteria_bundle']['bundle_summary']
        assert pack['release_decision_freeze_artifact_pack']['contract_version'] == 'release-decision-freeze-artifact-pack.v1'
        assert pack['release_decision_freeze_artifact_pack']['decision'] in {'go', 'no_go'}
        assert pack['release_decision_freeze_artifact_pack']['freeze_artifact']
        assert pack['handoff_approval_record_pack']['contract_version'] == 'handoff-approval-record-pack.v1'
        assert pack['handoff_approval_record_pack']['approval_status']
        assert pack['handoff_approval_record_pack']['handoff_record']
        assert pack['operator_release_brief_pack']['contract_version'] == 'operator-release-brief-pack.v1'
        assert pack['operator_release_brief_pack']['brief_summary']
        assert pack['operator_release_brief_pack']['operator_status']
        assert pack['release_ops_runbook_pack']['contract_version'] == 'release-ops-runbook-pack.v1'
        assert pack['release_ops_runbook_pack']['runbook_steps']
        assert 'rollback_note' in pack['release_ops_runbook_pack']
        assert pack['incident_rollback_pack']['contract_version'] == 'incident-rollback-pack.v1'
        assert pack['incident_rollback_pack']['rollback_steps']
        assert pack['incident_rollback_pack']['rollback_target']
        assert pack['postmortem_recovery_record_pack']['contract_version'] == 'postmortem-recovery-record-pack.v1'
        assert pack['postmortem_recovery_record_pack']['recovery_record']
        assert pack['postmortem_recovery_record_pack']['postmortem_summary']
        assert pack['recovery_closure_artifact_pack']['contract_version'] == 'recovery-closure-artifact-pack.v1'
        assert pack['recovery_closure_artifact_pack']['closure_status']
        assert pack['recovery_closure_artifact_pack']['closure_record']
        assert pack['final_governance_summary_pack']['contract_version'] == 'final-governance-summary-pack.v1'
        assert pack['final_governance_summary_pack']['governance_summary']
        assert pack['final_governance_summary_pack']['governance_status']
        assert pack['governance_dashboard_pack']['contract_version'] == 'governance-dashboard-pack.v1'
        assert pack['governance_dashboard_pack']['dashboard_status']
        assert pack['governance_dashboard_pack']['summary_card']
        assert pack['release_review_note_pack']['contract_version'] == 'release-review-note-pack.v1'
        assert pack['release_review_note_pack']['note_text']
        assert 'whole_book_consistency_release_impact' in pack['release_review_note_pack']['note_text']
        assert pack['approval_decision_memo_pack']['contract_version'] == 'approval-decision-memo-pack.v1'
        assert pack['approval_decision_memo_pack']['memo_text']
        assert 'whole_book_release_impact' in pack['approval_decision_memo_pack']['memo_text']
        assert pack['approval_decision_memo_pack']['memo_status']
        assert pack['external_report_bundle_pack']['contract_version'] == 'external-report-bundle-pack.v1'
        assert 'dashboard' in pack['external_report_bundle_pack']
        assert 'approval_memo' in pack['external_report_bundle_pack']
        assert pack['audit_conclusion']
        assert pack['review_summary'] is not None
        assert pack['risk_summary'] is not None
        assert pack['recommended_next_actions']
