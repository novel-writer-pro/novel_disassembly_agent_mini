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
    lines.extend(['', '## Graph Overview'])
    lines.append(f'- nodes: {len(graph_nodes)}')
    lines.append(f'- edges: {len(graph_edges)}')
    if graph_nodes:
        lines.append('')
        lines.append('Top Nodes:')
        for node in graph_nodes[:10]:
            lines.append(
                f"- {node.get('node_type')}:{node.get('label')} "
                f"(seen {node.get('occurrence_count')})"
            )
    return '\n'.join(lines).strip() + '\n'
