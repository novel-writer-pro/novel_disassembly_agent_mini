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


def test_graph_materialization_creates_nodes_edges_and_progression(tmp_path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        service = GraphService(session)
        artifact1 = RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '命格初现',
                'chapter_summary': '卫图觉醒命格。',
                'key_entities': ['卫图', '命格', '养生功'],
                'key_events': ['卫图觉醒命格'],
                'continuity_notes': [],
                'writer_learning_notes': [],
                'unsupported_inferences': [],
                'ambiguous_points': [],
                'needs_human_review': False,
                'quality_gate_notes': [],
                'hook_score': 4.0,
                'dimensions': [],
            },
        )
        artifact2 = RunService(session).record_chapter_artifact(
            branch.id,
            2,
            {
                'chapter_index': 2,
                'normalized_title': '线索推进',
                'chapter_summary': '卫图去找二姑。',
                'key_entities': ['卫图', '二姑'],
                'key_events': ['卫图去找二姑'],
                'continuity_notes': [],
                'writer_learning_notes': [],
                'unsupported_inferences': [],
                'ambiguous_points': [],
                'needs_human_review': False,
                'quality_gate_notes': [],
                'hook_score': 4.0,
                'dimensions': [],
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
        assert stored_nodes
        assert stored_edges
        summary = service.summarize_branch(branch.id)
        assert summary.top_entities
        assert summary.progression_edges
