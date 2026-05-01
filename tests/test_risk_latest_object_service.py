from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ChapterArtifact
from novel_analyzer.database.session import create_schema
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.risk_latest_object_service import RiskLatestObjectService
from novel_analyzer.services.run_service import RunService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def test_risk_latest_object_service_reads_state_summary_snapshots(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '前文基线',
                'chapter_summary': '前文已有关系、规则、冲突。',
                'key_entities': ['卫图'],
                'key_events': ['关系与规则变化'],
                'state_summary': {
                    'evolved_relations': ['卫图与族兄关系缓和'],
                    'constraining_world_rules': ['外城访客不得直接调动全城阵法'],
                    'escalated_conflicts': ['卫图与城主府矛盾进一步激化'],
                },
                'needs_human_review': True,
                'dimensions': [],
                'quality_gate_notes': [],
            },
        )
        artifact = session.scalar(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch.id)
            .where(ChapterArtifact.chapter_index == 1)
        )
        GraphService(session).materialize_for_artifact(artifact.id)
        service = RiskLatestObjectService(session)
        snapshots = service.latest_snapshots(branch_id=branch.id, chapter_index=2)
        assert snapshots
        types = {item.object_type for item in snapshots}
        assert 'relationship' in types or 'rule_scope' in types or 'conflict_thread' in types
