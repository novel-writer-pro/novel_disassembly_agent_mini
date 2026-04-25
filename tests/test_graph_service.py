import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import GraphEdge, GraphNode
from novel_analyzer.database.session import create_schema
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.run_service import RunService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def _artifact_payload(
    chapter_index: int,
    *,
    title: str,
    summary: str,
    entities: list[str],
    events: list[str],
) -> dict[str, object]:
    return {
        'chapter_index': chapter_index,
        'normalized_title': title,
        'chapter_summary': summary,
        'key_entities': entities,
        'key_events': events,
        'continuity_notes': [f'第{chapter_index}章衔接'],
        'writer_learning_notes': [],
        'unsupported_inferences': [],
        'ambiguous_points': [],
        'needs_human_review': False,
        'quality_gate_notes': [],
        'hook_score': 4.0,
        'dimensions': [],
    }


def _record_stage_payload(
    session: Session,
    run_id: str,
    branch_id: str,
    chapter_index: int,
    payload: dict[str, object],
    *,
    job_attempt: int = 1,
) -> None:
    RunService(session).record_raw_output(
        run_id,
        branch_id,
        chapter_index,
        job_attempt,
        json.dumps(payload, ensure_ascii=False),
        parsed_json={'ok': True},
        parse_status='parsed',
        parse_error=None,
        invocation_metadata={'pipeline': 'test'},
    )


def test_graph_materialization_builds_reasoning_nodes_edges_and_summary(tmp_path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        service = GraphService(session)
        artifact1 = RunService(session).record_chapter_artifact(
            branch.id,
            1,
            _artifact_payload(
                1,
                title='命格初现',
                summary='卫图觉醒命格。',
                entities=['卫图', '命格'],
                events=['卫图觉醒命格'],
            ),
        )
        _record_stage_payload(
            session,
            run.id,
            branch.id,
            1,
            {
                'facts': {
                    'characters': [
                        {'label': '卫图', 'evidence': ['卫图'], 'confidence': 0.98}
                    ],
                    'events': [
                        {'label': '卫图觉醒命格', 'evidence': ['命格初现'], 'confidence': 0.97}
                    ],
                    'relations': [
                        {'label': '卫图与命格建立联系', 'evidence': ['命格'], 'confidence': 0.8}
                    ],
                    'conflicts': [
                        {'label': '卫图受限于出身', 'evidence': ['寒门'], 'confidence': 0.72}
                    ],
                    'foreshadowing': [
                        {
                            'label': '命格后续将改变命运',
                            'evidence': ['大器晚成'],
                            'confidence': 0.76,
                        }
                    ],
                    'worldbuilding_facts': [
                        {'label': '命格决定成长路径', 'evidence': ['命格'], 'confidence': 0.81}
                    ],
                },
                'analysis': {'continuity_notes': ['命格线已开启']},
            },
        )
        artifact2 = RunService(session).record_chapter_artifact(
            branch.id,
            2,
            _artifact_payload(
                2,
                title='命格兑现',
                summary='卫图因命格得到机缘。',
                entities=['卫图', '命格'],
                events=['卫图因命格得到机缘'],
            ),
        )
        _record_stage_payload(
            session,
            run.id,
            branch.id,
            2,
            {
                'facts': {
                    'characters': [
                        {'label': '卫图', 'evidence': ['卫图'], 'confidence': 0.98}
                    ],
                    'events': [
                        {
                            'label': '卫图因命格得到机缘',
                            'evidence': ['机缘'],
                            'confidence': 0.93,
                        }
                    ],
                    'relations': [
                        {'label': '卫图借命格翻身', 'evidence': ['命格'], 'confidence': 0.82}
                    ],
                    'conflicts': [
                        {'label': '卫图仍受家境掣肘', 'evidence': ['家境'], 'confidence': 0.68}
                    ],
                    'foreshadowing': [],
                    'worldbuilding_facts': [
                        {'label': '命格会影响机缘分配', 'evidence': ['机缘'], 'confidence': 0.8}
                    ],
                },
                'analysis': {'continuity_notes': ['命格开始兑现']},
            },
        )
        service.materialize_for_artifact(artifact1.id)
        nodes, edges = service.materialize_for_artifact(artifact2.id)

        assert nodes
        assert edges
        stored_nodes = session.scalars(
            select(GraphNode).where(GraphNode.branch_id == branch.id)
        ).all()
        stored_edges = session.scalars(
            select(GraphEdge).where(GraphEdge.branch_id == branch.id)
        ).all()
        node_types = {node.node_type for node in stored_nodes}
        edge_types = {edge.edge_type for edge in stored_edges}
        assert {
            'entity',
            'event',
            'relation',
            'conflict',
            'foreshadow',
            'world_rule',
            'continuity',
        } <= node_types
        assert {'participates_in', 'follows', 'pays_off_as', 'constrains'} <= edge_types

        summary = service.summarize_branch(branch.id)
        snapshot = service.reasoning_snapshot(branch.id)
        assert summary.top_entities
        assert summary.progression_edges
        assert summary.reasoning_paths
        assert summary.open_foreshadowing == []
        assert summary.active_conflicts
        assert summary.world_rules
        assert snapshot['state_machine']['foreshadow']
        assert any(
            item['status'] == 'paid_off' for item in snapshot['state_machine']['foreshadow']
        )
        assert any(
            item['status'] == 'escalated' for item in snapshot['state_machine']['conflict']
        )
        assert any(
            item['status'] == 'evolved' for item in snapshot['state_machine']['relation']
        )


def test_graph_materialization_rebuilds_branch_state_when_chapter_is_replaced(tmp_path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        service = GraphService(session)
        artifact1 = RunService(session).record_chapter_artifact(
            branch.id,
            1,
            _artifact_payload(
                1,
                title='旧标题',
                summary='旧事件。',
                entities=['卫图'],
                events=['旧事件'],
            ),
        )
        _record_stage_payload(
            session,
            run.id,
            branch.id,
            1,
            {'facts': {'characters': [{'label': '卫图'}], 'events': [{'label': '旧事件'}]}},
        )
        service.materialize_for_artifact(artifact1.id)
        initial_snapshot = service.reasoning_snapshot(branch.id)
        assert any(node['label'] == '旧事件' for node in initial_snapshot['nodes'])

        artifact2 = RunService(session).record_chapter_artifact(
            branch.id,
            1,
            _artifact_payload(
                1,
                title='新标题',
                summary='新事件。',
                entities=['卫图'],
                events=['新事件'],
            ),
        )
        _record_stage_payload(
            session,
            run.id,
            branch.id,
            1,
            {'facts': {'characters': [{'label': '卫图'}], 'events': [{'label': '新事件'}]}},
            job_attempt=2,
        )
        service.materialize_for_artifact(artifact2.id)
        rebuilt_snapshot = service.reasoning_snapshot(branch.id)
        labels = {node['label'] for node in rebuilt_snapshot['nodes']}
        assert '新事件' in labels
        assert '旧事件' not in labels
