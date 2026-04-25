"""Markdown reporting for branch-level operational summaries."""

from __future__ import annotations

from typing import Any


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
                f"review={row.get('needs_human_review')}"
            )
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
