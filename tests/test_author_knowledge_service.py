from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novel_analyzer.database.session import create_schema
from novel_analyzer.services.fact_service import FactService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.run_service import RunService
from novel_analyzer.services.author_knowledge_service import AuthorKnowledgeService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def test_author_knowledge_service_builds_branch_knowledge_pack(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        fact_service = FactService(session)
        graph_service = GraphService(session)
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

        pack = AuthorKnowledgeService(session).build_branch_knowledge_pack(branch.id)
        assert pack['contract_version'] == 'author-knowledge.v1'
        assert pack['chapter_span']['count'] == 2
        assert pack['entities']
        assert pack['events']
        assert pack['chapter_cards']
        assert pack['knowledge_index']
        assert pack['entity_profiles'] is not None
        assert pack['relationship_index'] is not None
        assert pack['rule_index'] is not None
        assert pack['thread_index'] is not None
        assert pack['summary_layer']
        assert pack['relationship_watch'] is not None
        assert pack['rule_watch'] is not None
        assert pack['unresolved_threads'] is not None
        assert pack['graph_overview']
        assert pack['recommended_questions']


def test_author_knowledge_service_supports_focus_label_and_chapter_range(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        fact_service = FactService(session)
        graph_service = GraphService(session)
        for idx, title, summary, entities in [
            (1, '命格初现', '卫图觉醒命格', ['卫图', '命格']),
            (2, '资源铺垫', '二姑帮卫图筹措资源', ['二姑', '卫图']),
            (3, '婚事推进', '卫图面临婚事压力', ['卫图', '婚事']),
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

        pack = AuthorKnowledgeService(session).build_branch_knowledge_pack(
            branch.id,
            from_chapter_index=2,
            upto_chapter_index=3,
            focus_label='卫图',
        )
        assert pack['focus_label'] == '卫图'
        assert pack['chapter_span']['min'] == 2
        assert pack['chapter_span']['max'] == 3
        assert all('卫图' in item['label'] for item in pack['entities'])
        assert all('卫图' in item['label'] for item in pack['entity_profiles'])
        assert pack['summary_layer']['top_entities']
