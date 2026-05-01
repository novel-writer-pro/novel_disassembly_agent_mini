from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import RiskSemanticSignalRecord
from novel_analyzer.database.session import create_schema
from novel_analyzer.embedding.service import DeterministicStubEmbeddingProvider
from novel_analyzer.services.risk_signal_link_service import RiskSignalLinkService
from novel_analyzer.services.risk_signal_store_service import RiskSignalStoreService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def test_risk_signal_store_service_persists_branch_chapter_signals() -> None:
    with _session() as session:
        service = RiskSignalStoreService(session)
        stored = service.replace_branch_chapter_signals(
            branch_id='branch-x',
            chapter_index=3,
            items=[
                {
                    'signal_type': 'relationship',
                    'source_field': 'state_summary.evolved_relations',
                    'raw_text': '卫图与族兄突然结盟',
                    'canonical_label': '关系缓和',
                    'canonical_group': 'relationship-soften',
                    'confidence': 0.72,
                    'vector_payload': [0.1, 0.2, 0.3],
                }
            ],
        )
        assert len(stored) == 1
        rows = service.list_branch_chapter_signals('branch-x', 3)
        assert len(rows) == 1
        assert rows[0].signal_type == 'relationship'
        assert rows[0].canonical_label == '关系缓和'


def test_risk_signal_link_service_persists_branch_links() -> None:
    with _session() as session:
        service = RiskSignalLinkService(session)
        stored = service.replace_branch_links(
            branch_id='branch-x',
            items=[
                {
                    'from_signal_id': 'sig-a',
                    'to_signal_id': 'sig-b',
                    'link_type': 'payoff_of',
                    'score': 0.83,
                    'evidence_json': {'reason': 'semantic-match'},
                }
            ],
        )
        assert len(stored) == 1
        rows = service.list_branch_links('branch-x')
        assert len(rows) == 1
        assert rows[0].link_type == 'payoff_of'
        assert rows[0].score == 0.83
        assert rows[0].chapter_index == 0


def test_build_signal_items_collects_state_and_checker_signals() -> None:
    items = RiskSignalStoreService.build_signal_items(
        artifact_payload={
            'state_summary': {
                'evolved_relations': ['卫图与族兄突然结盟'],
                'new_foreshadowing': ['古符异动伏笔'],
            },
            'unsupported_inferences': ['外城访客可无条件调动阵法缺少证据'],
        },
        checker_results=[
            {
                'checker_name': 'relationship_consistency',
                'risks': [
                    {
                        'risk_type': 'trust_state_conflict',
                        'summary': '关系状态冲突',
                        'confidence': 0.35,
                    }
                ],
            }
        ],
    )
    signal_types = {item['signal_type'] for item in items}
    assert 'relationship' in signal_types
    assert 'foreshadow' in signal_types
    assert 'unsupported' in signal_types
    assert 'checker:relationship_consistency' in signal_types


def test_risk_signal_store_service_fills_embedding_vectors_when_missing() -> None:
    with _session() as session:
        service = RiskSignalStoreService(session)
        service.embedding_provider = DeterministicStubEmbeddingProvider(dim=8)
        stored = service.replace_branch_chapter_signals(
            branch_id='branch-y',
            chapter_index=5,
            items=[
                {
                    'signal_type': 'foreshadow',
                    'source_field': 'state_summary.new_foreshadowing',
                    'raw_text': '古符异动伏笔',
                    'canonical_label': '古符异动伏笔',
                    'canonical_group': 'foreshadow',
                    'confidence': 0.5,
                }
            ],
        )
        assert len(stored) == 1
        rows = service.list_branch_chapter_signals('branch-y', 5)
        assert len(rows) == 1
        db_row = session.scalar(
            select(RiskSemanticSignalRecord)
            .where(RiskSemanticSignalRecord.branch_id == 'branch-y')
            .where(RiskSemanticSignalRecord.chapter_index == 5)
        )
        assert db_row is not None
        assert db_row.vector_dim == 8
        assert len(db_row.vector_payload) == 8
        assert db_row.vector_text.startswith('[')


def test_risk_signal_store_service_semantic_search_returns_matching_signal() -> None:
    with _session() as session:
        service = RiskSignalStoreService(session)
        service.embedding_provider = DeterministicStubEmbeddingProvider(dim=8)
        service.replace_branch_chapter_signals(
            branch_id='branch-z',
            chapter_index=8,
            items=[
                {
                    'signal_type': 'relationship',
                    'source_field': 'state_summary.evolved_relations',
                    'raw_text': '卫图与族兄突然结盟',
                    'canonical_label': '关系缓和',
                    'canonical_group': 'relationship-soften',
                    'confidence': 0.7,
                },
                {
                    'signal_type': 'foreshadow',
                    'source_field': 'state_summary.new_foreshadowing',
                    'raw_text': '古符异动伏笔',
                    'canonical_label': '古符异动伏笔',
                    'canonical_group': 'foreshadow',
                    'confidence': 0.6,
                },
            ],
        )
        hits = service.semantic_search(
            branch_id='branch-z',
            query_text='卫图和族兄关系突然缓和',
            signal_type='relationship',
            limit=3,
        )
        assert hits
        assert hits[0].signal_type == 'relationship'


def test_risk_signal_store_service_semantic_search_can_filter_to_prior_chapters() -> None:
    with _session() as session:
        service = RiskSignalStoreService(session)
        service.embedding_provider = DeterministicStubEmbeddingProvider(dim=8)
        service.replace_branch_chapter_signals(
            branch_id='branch-h',
            chapter_index=1,
            items=[
                {
                    'signal_type': 'relationship',
                    'source_field': 'state_summary.evolved_relations',
                    'raw_text': '卫图与族兄关系缓和',
                    'canonical_label': '关系缓和',
                    'canonical_group': 'relationship-soften',
                    'confidence': 0.7,
                }
            ],
        )
        service.replace_branch_chapter_signals(
            branch_id='branch-h',
            chapter_index=2,
            items=[
                {
                    'signal_type': 'relationship',
                    'source_field': 'state_summary.evolved_relations',
                    'raw_text': '卫图与族兄突然结盟',
                    'canonical_label': '关系缓和',
                    'canonical_group': 'relationship-soften',
                    'confidence': 0.7,
                }
            ],
        )
        hits = service.semantic_search(
            branch_id='branch-h',
            query_text='卫图和族兄关系突然缓和',
            signal_type='relationship',
            before_chapter_index=2,
            limit=5,
        )
        assert hits
        assert all(hit.chapter_index < 2 for hit in hits)


def test_risk_signal_store_service_list_latest_signals_returns_prior_history() -> None:
    with _session() as session:
        service = RiskSignalStoreService(session)
        service.replace_branch_chapter_signals(
            branch_id='branch-latest',
            chapter_index=1,
            items=[{'signal_type': 'relationship', 'raw_text': '卫图与族兄关系缓和', 'canonical_label': '关系缓和'}],
        )
        service.replace_branch_chapter_signals(
            branch_id='branch-latest',
            chapter_index=2,
            items=[{'signal_type': 'relationship', 'raw_text': '卫图与族兄突然结盟', 'canonical_label': '关系缓和'}],
        )
        hits = service.list_latest_signals(
            branch_id='branch-latest',
            signal_type='relationship',
            before_chapter_index=3,
            limit=5,
        )
        assert hits
        assert hits[0].chapter_index == 2


def test_risk_signal_store_service_semantic_search_sqlite_fallback_still_works() -> None:
    with _session() as session:
        service = RiskSignalStoreService(session)
        service.embedding_provider = DeterministicStubEmbeddingProvider(dim=8)
        service.replace_branch_chapter_signals(
            branch_id='branch-sqlite',
            chapter_index=1,
            items=[
                {
                    'signal_type': 'rule_scope',
                    'source_field': 'state_summary.constraining_world_rules',
                    'raw_text': '外城访客不得直接调动全城阵法',
                    'canonical_label': '访客权限受限',
                    'canonical_group': 'rule_scope',
                    'confidence': 0.7,
                }
            ],
        )
        hits = service.semantic_search(
            branch_id='branch-sqlite',
            query_text='访客不能直接动用全城阵法',
            signal_type='rule_scope',
            limit=3,
        )
        assert hits
        assert hits[0].signal_type == 'rule_scope'


def test_risk_signal_link_service_builds_minimal_link_proposals() -> None:
    with _session() as session:
        service = RiskSignalLinkService(session)
        proposals = service.build_minimal_link_proposals(
            branch_id='branch-link',
            chapter_index=12,
            signals=[
                {'id': 'sig-1', 'signal_type': 'foreshadow', 'raw_text': '古符异动伏笔'},
                {'id': 'sig-2', 'signal_type': 'checker:foreshadow_payoff_consistency', 'raw_text': '伏笔突然兑现'},
            ],
        )
        assert proposals
        assert proposals[0]['link_type'] == 'payoff_of'
        assert proposals[0]['chapter_index'] == 12
