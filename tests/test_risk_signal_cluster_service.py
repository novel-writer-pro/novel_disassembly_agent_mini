from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novel_analyzer.database.models import RiskSemanticSignalRecord
from novel_analyzer.database.session import create_schema
from novel_analyzer.services.risk_signal_cluster_service import RiskSignalClusterService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def test_risk_signal_cluster_service_builds_and_persists_clusters() -> None:
    with _session() as session:
        session.add_all(
            [
                RiskSemanticSignalRecord(
                    branch_id='branch-c',
                    chapter_index=2,
                    signal_type='relationship',
                    raw_text='卫图与族兄突然结盟',
                    canonical_label='关系缓和',
                    canonical_group='relationship-soften',
                ),
                RiskSemanticSignalRecord(
                    branch_id='branch-c',
                    chapter_index=2,
                    signal_type='relationship',
                    raw_text='卫图与族兄关系缓和',
                    canonical_label='关系缓和',
                    canonical_group='relationship-soften',
                ),
            ]
        )
        session.commit()
        service = RiskSignalClusterService(session)
        clusters = service.build_clusters_from_signals(branch_id='branch-c', chapter_index=2)
        assert clusters
        stored = service.replace_branch_chapter_clusters(branch_id='branch-c', chapter_index=2, clusters=clusters)
        assert stored
        rows = service.list_branch_chapter_clusters('branch-c', 2)
        assert len(rows) == 1
        assert rows[0].signal_type == 'relationship'
        assert len(rows[0].signal_ids) == 2


def test_risk_signal_cluster_service_lists_latest_prior_clusters() -> None:
    with _session() as session:
        session.add_all(
            [
                RiskSemanticSignalRecord(
                    branch_id='branch-lc',
                    chapter_index=1,
                    signal_type='foreshadow',
                    raw_text='古符异动伏笔',
                    canonical_label='古符异动伏笔',
                    canonical_group='foreshadow',
                ),
                RiskSemanticSignalRecord(
                    branch_id='branch-lc',
                    chapter_index=2,
                    signal_type='foreshadow',
                    raw_text='古符异动再次提及',
                    canonical_label='古符异动伏笔',
                    canonical_group='foreshadow',
                ),
            ]
        )
        session.commit()
        service = RiskSignalClusterService(session)
        service.replace_branch_chapter_clusters(
            branch_id='branch-lc',
            chapter_index=1,
            clusters=service.build_clusters_from_signals(branch_id='branch-lc', chapter_index=1),
        )
        service.replace_branch_chapter_clusters(
            branch_id='branch-lc',
            chapter_index=2,
            clusters=service.build_clusters_from_signals(branch_id='branch-lc', chapter_index=2),
        )
        rows = service.list_latest_clusters(
            branch_id='branch-lc',
            signal_type='foreshadow',
            before_chapter_index=3,
            limit=5,
        )
        assert rows
        assert rows[0].signal_type == 'foreshadow'
