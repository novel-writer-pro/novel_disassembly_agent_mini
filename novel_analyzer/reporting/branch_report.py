"""Markdown reporting for branch-level operational summaries."""

from __future__ import annotations

from typing import Any


_RISK_SEVERITY_ORDER = {
    None: -1,
    'low': 0,
    'medium': 1,
    'high': 2,
    'critical': 3,
}

_CLUSTER_STATUS_LABEL = {
    'open': '待观察',
    'needs_review': '待复核',
    'reviewed': '已复核',
    'escalated': '已升级',
    'reopened': '重新打开',
    'resolved': '已关闭',
}


def render_branch_report(bundle: dict[str, Any]) -> str:
    """Render a branch bundle into human-readable Markdown."""

    status = bundle.get('status', {})
    lines = [
        '# Branch Report',
        '',
        '## Status',
    ]
    for key in [
        'run_id',
        'branch_id',
        'branch_name',
        'branch_status',
        'manifest_chapter_count',
        'completed_chapters',
        'failed_jobs',
        'running_jobs',
        'next_chapter',
        'fact_count',
        'window_count',
        'graph_node_count',
        'graph_edge_count',
    ]:
        lines.append(f'- {key}: {status.get(key)}')
    audit_conclusion = bundle.get('audit_conclusion')
    if audit_conclusion:
        lines.extend(['', '## Audit Conclusion'])
        if isinstance(audit_conclusion, dict):
            mapping = [
                ('content_judgement', 'Content Judgement'),
                ('risk_judgement', 'Risk Judgement'),
                ('blocking_judgement', 'Blocking Judgement'),
                ('recommended_action', 'Recommended Action'),
            ]
            for key, label in mapping:
                value = audit_conclusion.get(key)
                if value:
                    lines.append(f'- {label}: {value}')
            progress_note = audit_conclusion.get('review_progress_note')
            if progress_note:
                lines.append(f'- Review Progress: {progress_note}')
            needs_review_note = audit_conclusion.get('needs_review_note')
            if needs_review_note:
                lines.append(f'- Needs Review: {needs_review_note}')
            resolved_cluster_note = audit_conclusion.get('resolved_cluster_note')
            if resolved_cluster_note:
                lines.append(f'- Resolved Clusters: {resolved_cluster_note}')
            result_note = audit_conclusion.get('review_result_note')
            if result_note:
                lines.append(f'- Review Result: {result_note}')
            pending_escalation_note = audit_conclusion.get('pending_escalation_note')
            if pending_escalation_note:
                lines.append(f'- Pending Escalation: {pending_escalation_note}')
            storage_note = audit_conclusion.get('review_storage_note')
            if storage_note:
                lines.append(f'- Review Storage: {storage_note}')
            owner_note = audit_conclusion.get('review_owner_note')
            if owner_note:
                lines.append(f'- Review Owner: {owner_note}')
            current_owner_note = audit_conclusion.get('current_owner_note')
            if current_owner_note:
                lines.append(f'- Current Owner: {current_owner_note}')
            actor_note = audit_conclusion.get('review_actor_note')
            if actor_note:
                lines.append(f'- Review Actor: {actor_note}')
            latest_event_type_note = audit_conclusion.get('latest_event_type_note')
            if latest_event_type_note:
                lines.append(f'- Latest Event Type: {latest_event_type_note}')
            pending_assignment_note = audit_conclusion.get('pending_assignment_note')
            if pending_assignment_note:
                lines.append(f'- Pending Assignment: {pending_assignment_note}')
            latest_review_note = audit_conclusion.get('latest_review_note')
            if latest_review_note:
                lines.append(f'- Latest Review: {latest_review_note}')
        else:
            lines.append(str(audit_conclusion))

    chapter_index = bundle.get('chapter_index', [])
    lines.extend(['', '## Chapter Index'])
    if not chapter_index:
        lines.append('- none')
    else:
        for row in chapter_index[:20]:
            lines.append(
                f"- chapter {row.get('chapter_index')}: {row.get('title')} | "
                f"job={row.get('job_status')} | artifact={row.get('has_artifact')} | "
                f"retrieval={row.get('has_retrieval')} | hook={row.get('hook_score')} | "
                f"review={row.get('needs_human_review')} | "
                f"risk={row.get('risk_level')} | risk_count={row.get('risk_count')}"
            )
    failed_summary = bundle.get('failed_summary', [])
    if isinstance(failed_summary, list):
        lines.extend(['', '## Failed Summary'])
        if not failed_summary:
            lines.append('- none')
        else:
            for item in failed_summary[:20]:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    f"- chapter {item.get('chapter_index')}: attempts={item.get('attempts')} | "
                    f"failure_class={item.get('failure_class')} | "
                    f"failure_code={item.get('failure_code')} | "
                    f"error={item.get('error')}"
                )
    risk_summary = bundle.get('risk_summary', {})
    if isinstance(risk_summary, dict):
        lines.extend(['', '## Risk Summary'])
        for key in [
            'risk_card_count',
            'checker_result_count',
            'review_candidate_count',
            'high_risk_chapters',
            'risk_counts_by_domain',
            'risk_counts_by_severity',
        ]:
            lines.append(f'- {key}: {risk_summary.get(key)}')

        high_risk_chapters = risk_summary.get('high_risk_chapters', [])
        if isinstance(high_risk_chapters, list) and high_risk_chapters:
            lines.append('')
            lines.append('### High Risk Chapters')
            for chapter in high_risk_chapters[:20]:
                lines.append(f'- chapter {chapter}')

        candidate_rows = [
            row for row in chapter_index
            if (row.get('risk_count') or 0) > 0 or row.get('needs_human_review')
        ]
        if candidate_rows:
            candidate_rows = sorted(
                candidate_rows,
                key=lambda row: (
                    -_RISK_SEVERITY_ORDER.get(row.get('risk_level'), -1),
                    -(row.get('risk_count') or 0),
                    0 if row.get('needs_human_review') else 1,
                    row.get('chapter_index') or 0,
                ),
            )
            lines.append('')
            lines.append('### Human Review Candidates')
            for row in candidate_rows[:20]:
                lines.append(
                    f"- chapter {row.get('chapter_index')}: risk={row.get('risk_level')} | "
                    f"risk_count={row.get('risk_count')} | review={row.get('needs_human_review')} | "
                    f"title={row.get('title')}"
                )
        review_candidates_summary = risk_summary.get('review_candidates_summary', [])
        if isinstance(review_candidates_summary, list) and review_candidates_summary:
            lines.append('')
            lines.append('### Review Candidate Evidence Preview')
            for item in review_candidates_summary[:12]:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    f"- chapter {item.get('chapter_index')} | checkers={item.get('checker_names')} | "
                    f"types={item.get('risk_types')} | risk={item.get('overall_risk_level')} | "
                    f"confidence={item.get('confidence')}"
                )
                summary = item.get('summary')
                if summary:
                    lines.append(f"  - summary: {summary}")
                for evidence in item.get('supporting_evidence_preview', [])[:2]:
                    lines.append(f"  - evidence: {evidence}")
                for evidence in item.get('counter_evidence_preview', [])[:1]:
                    lines.append(f"  - counter: {evidence}")
                for evidence in item.get('continuity_evidence_preview', [])[:2]:
                    lines.append(f"  - continuity: {evidence}")
                for evidence in item.get('branch_signal_preview', [])[:2]:
                    lines.append(f"  - branch-signal: {evidence}")
        review_candidate_clusters = risk_summary.get('review_candidate_clusters', [])
        if isinstance(review_candidate_clusters, list) and review_candidate_clusters:
            lines.append('')
            lines.append('### Review Candidate Clusters')
            for item in review_candidate_clusters[:12]:
                if not isinstance(item, dict):
                    continue
                status_value = str(item.get('cluster_status') or '')
                status_label = _CLUSTER_STATUS_LABEL.get(status_value, status_value or '未知')
                lines.append(
                    f"- status={status_value} ({status_label}) | priority={item.get('review_priority')} | pattern={item.get('pattern_label')} | title={item.get('cluster_title')} | checkers={item.get('checker_names')} | types={item.get('risk_types')} | "
                    f"chapters={item.get('chapters')} | span={item.get('chapter_span')} | chapter_count={item.get('chapter_count')} | "
                    f"confidence={item.get('max_confidence')}"
                )
                if item.get('sample_summary'):
                    lines.append(f"  - sample: {item.get('sample_summary')}")
                if item.get('suggested_review_action'):
                    lines.append(f"  - action: {item.get('suggested_review_action')}")
                if item.get('workflow_lane'):
                    lines.append(f"  - workflow_lane: {item.get('workflow_lane')}")
                if item.get('queue_priority'):
                    lines.append(f"  - queue_priority: {item.get('queue_priority')}")
                if 'action_required' in item:
                    lines.append(f"  - action_required: {item.get('action_required')}")
                if item.get('suggested_deadline_level'):
                    lines.append(f"  - suggested_deadline_level: {item.get('suggested_deadline_level')}")
                if item.get('batch_operation_hint'):
                    lines.append(f"  - batch_operation_hint: {item.get('batch_operation_hint')}")
                if item.get('auto_next_action'):
                    lines.append(f"  - auto_next_action: {item.get('auto_next_action')}")
                if item.get('escalation_reason'):
                    lines.append(f"  - escalation_reason: {item.get('escalation_reason')}")
                if item.get('review_owner'):
                    lines.append(f"  - owner: {item.get('review_owner')}")
                if item.get('resolved_at'):
                    lines.append(f"  - resolved_at: {item.get('resolved_at')}")
                if item.get('review_result'):
                    lines.append(
                        f"  - result: {item.get('review_result')} ({item.get('review_result_label') or '未映射'})"
                    )
                if item.get('review_notes'):
                    lines.append(f"  - notes: {item.get('review_notes')}")
                if item.get('review_history_count') is not None:
                    lines.append(f"  - history_count: {item.get('review_history_count')}")
                latest_event = item.get('latest_review_event')
                if isinstance(latest_event, dict):
                    lines.append(
                        f"  - latest_event: from={latest_event.get('previous_cluster_status')}->{latest_event.get('cluster_status')} | "
                        f"result={latest_event.get('review_result')} | owner={latest_event.get('review_owner')} | "
                        f"actor={latest_event.get('review_actor') or latest_event.get('review_owner')} | "
                        f"created_at={latest_event.get('created_at')}"
                    )
            phase2_clusters = [
                item for item in review_candidate_clusters
                if isinstance(item, dict)
                and any(
                    risk_type in {
                        'thread_state_conflict',
                        'motivation_to_action_gap',
                        'sequence_conflict_candidate',
                        'recovery_window_insufficient',
                        'upset_without_setup',
                        'cost_constraint_missing',
                    }
                    for risk_type in item.get('risk_types', [])
                )
            ]
            if phase2_clusters:
                lines.append('')
                lines.append('### Phase-2 Risk Highlights')
                for item in phase2_clusters[:8]:
                    lines.append(
                        f"- title={item.get('cluster_title')} | types={item.get('risk_types')} | "
                        f"chapters={item.get('chapters')} | priority={item.get('review_priority')} | "
                        f"pattern={item.get('pattern_label')}"
                    )
                    if item.get('suggested_review_action'):
                        lines.append(f"  - focus: {item.get('suggested_review_action')}")
    review_summary = bundle.get('review_summary', {})
    if isinstance(review_summary, dict) and review_summary:
        lines.extend(['', '## Review Summary'])
        for key in [
            'cluster_count',
            'history_event_count',
            'current_owner_top',
            'current_owner_top_count',
            'latest_actor_top',
            'latest_actor_top_count',
            'latest_event_type_top',
            'latest_event_type_top_count',
            'workflow_lane_top',
            'workflow_lane_top_count',
            'queue_priority_top',
            'queue_priority_top_count',
            'deadline_level_top',
            'deadline_level_top_count',
            'batch_operation_hint_top',
            'batch_operation_hint_top_count',
            'batch_suggestions',
            'auto_next_action_code_top',
            'auto_next_action_code_top_count',
            'auto_next_action_top',
            'auto_next_action_top_count',
            'escalation_reason_code_top',
            'escalation_reason_code_top_count',
            'escalation_reason_top',
            'escalation_reason_top_count',
            'phase2_focus_top',
            'phase2_focus_top_count',
            'pending_assignment_count',
            'pending_escalation_count',
            'resolved_count',
            'needs_review_count',
            'action_required_count',
        ]:
            if key in review_summary:
                lines.append(f'- {key}: {review_summary.get(key)}')
        for key in [
            'by_status',
            'by_result',
            'by_owner',
            'by_actor',
            'by_latest_event_type',
            'by_workflow_lane',
            'by_queue_priority',
            'by_deadline_level',
            'by_batch_operation_hint',
            'by_auto_next_action_code',
            'by_auto_next_action',
            'by_escalation_reason_code',
            'by_escalation_reason',
            'by_phase2_focus',
        ]:
            if key in review_summary:
                lines.append(f'- {key}: {review_summary.get(key)}')
    windows = bundle.get('windows', [])
    lines.extend(['', '## Windows'])
    if not windows:
        lines.append('- none')
    else:
        for window in windows:
            start = window.get('window_start_chapter')
            end = window.get('window_end_chapter')
            lines.append(f'### Window {start}-{end}')
            lines.append(window.get('window_summary', ''))
            lines.append('')

    graph_nodes = bundle.get('graph_nodes', [])
    graph_edges = bundle.get('graph_edges', [])
    reasoning_graph = bundle.get('reasoning_graph', {})
    state_summary = bundle.get('state_summary', {})
    chapter_output_summary = bundle.get('chapter_output_summary', {})
    overview = reasoning_graph.get('overview', {}) if isinstance(reasoning_graph, dict) else {}
    lines.extend(['', '## Graph Overview'])
    lines.append(f'- nodes: {len(graph_nodes)}')
    lines.append(f'- edges: {len(graph_edges)}')
    if overview:
        lines.append(f"- node types: {overview.get('node_type_counts', {})}")
        lines.append(f"- edge types: {overview.get('edge_type_counts', {})}")
    if graph_nodes:
        lines.append('')
        lines.append('Top Nodes:')
        for node in graph_nodes[:10]:
            lines.append(
                f"- {node.get('node_type')}:{node.get('label')} "
                f"(seen {node.get('occurrence_count')})"
            )
    if isinstance(state_summary, dict):
        lines.extend(['', '## State Summary'])
        for label, key in [
            ('新增伏笔', 'new_foreshadowing'),
            ('已回收伏笔', 'paid_off_foreshadowing'),
            ('新增冲突', 'new_conflicts'),
            ('冲突升级', 'escalated_conflicts'),
            ('关系变化', 'evolved_relations'),
            ('规则约束', 'constraining_world_rules'),
        ]:
            items = state_summary.get(key, [])
            if not isinstance(items, list) or not items:
                continue
            lines.append(f'### {label}')
            for item in items[:10]:
                lines.append(f'- {item}')
    if isinstance(chapter_output_summary, dict):
        lines.extend(['', '## Chapter Output Summary'])
        for heading, key in [
            ('推进摘要总览', 'state_transition_notes'),
            ('已解决线索总览', 'evidence_backed_resolutions'),
            ('未解线程总览', 'unresolved_threads'),
        ]:
            items = chapter_output_summary.get(key, [])
            if not isinstance(items, list) or not items:
                continue
            lines.append(f'### {heading}')
            for item in items[:12]:
                if isinstance(item, dict):
                    lines.append(
                        f"- 第{item.get('chapter_index')}章: {item.get('note')}"
                    )
    if isinstance(reasoning_graph, dict):
        lines.extend(['', '## Reasoning Graph'])
        central_nodes = reasoning_graph.get('central_nodes', [])
        if central_nodes:
            lines.append('### Central Nodes')
            for item in central_nodes[:8]:
                lines.append(
                    f"- {item.get('node_type')}:{item.get('label')} degree={item.get('degree')}"
                )
        reasoning_paths = reasoning_graph.get('reasoning_paths', [])
        if reasoning_paths:
            lines.append('')
            lines.append('### Reasoning Paths')
            for path in reasoning_paths[:12]:
                lines.append(f'- {path}')
        active_conflicts = reasoning_graph.get('active_conflicts', [])
        if active_conflicts:
            lines.append('')
            lines.append('### Active Conflicts')
            for item in active_conflicts[:10]:
                lines.append(f'- {item}')
        open_foreshadowing = reasoning_graph.get('open_foreshadowing', [])
        if open_foreshadowing:
            lines.append('')
            lines.append('### Open Foreshadowing')
            for item in open_foreshadowing[:10]:
                lines.append(f'- {item}')
        world_rules = reasoning_graph.get('world_rules', [])
        if world_rules:
            lines.append('')
            lines.append('### World Rules')
            for item in world_rules[:10]:
                lines.append(f'- {item}')
        state_machine = reasoning_graph.get('state_machine', {})
        if isinstance(state_machine, dict):
            for key, heading in [
                ('foreshadow', 'Foreshadow States'),
                ('conflict', 'Conflict States'),
                ('relation', 'Relation States'),
                ('world_rule', 'World Rule States'),
            ]:
                items = state_machine.get(key, [])
                if not items:
                    continue
                lines.append('')
                lines.append(f'### {heading}')
                for item in items[:10]:
                    lines.append(f"- {item.get('label')} [{item.get('status')}]")
    return '\n'.join(lines).strip() + '\n'
