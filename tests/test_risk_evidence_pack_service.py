from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import FactRecord
from novel_analyzer.database.session import create_schema
from novel_analyzer.embedding.service import DeterministicStubEmbeddingProvider
from novel_analyzer.services.risk_evidence_pack_service import RiskEvidencePackService
from novel_analyzer.services.risk_signal_cluster_service import RiskSignalClusterService
from novel_analyzer.services.risk_signal_link_service import RiskSignalLinkService
from novel_analyzer.services.risk_signal_store_service import RiskSignalStoreService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def test_risk_evidence_pack_service_collects_hits_and_link_types() -> None:
    with _session() as session:
        store = RiskSignalStoreService(session)
        store.embedding_provider = DeterministicStubEmbeddingProvider(dim=8)
        links = RiskSignalLinkService(session)
        stored = store.replace_branch_chapter_signals(
            branch_id='branch-pack',
            chapter_index=1,
            items=[
                {
                    'signal_type': 'foreshadow',
                    'source_field': 'state_summary.new_foreshadowing',
                    'raw_text': '古符异动伏笔',
                    'canonical_label': '古符异动伏笔',
                    'canonical_group': 'foreshadow',
                    'confidence': 0.6,
                },
                {
                    'signal_type': 'checker:foreshadow_payoff_consistency',
                    'source_field': 'checker_result.risks.summary',
                    'raw_text': '伏笔突然兑现',
                    'canonical_label': '伏笔突然兑现',
                    'canonical_group': 'payoff_without_setup',
                    'confidence': 0.7,
                },
            ],
        )
        links.replace_branch_links(
            branch_id='branch-pack',
            chapter_index=2,
            items=links.build_minimal_link_proposals(
                branch_id='branch-pack',
                chapter_index=2,
                signals=[
                    {
                        'id': s.id,
                        'signal_type': s.signal_type,
                        'raw_text': s.raw_text,
                    }
                    for s in stored
                ],
            ),
        )
        clusters = RiskSignalClusterService(session)
        clusters.replace_branch_chapter_clusters(
            branch_id='branch-pack',
            chapter_index=1,
            clusters=clusters.build_clusters_from_signals(branch_id='branch-pack', chapter_index=1),
        )
        pack_service = RiskEvidencePackService(session, store, links, clusters)
        pack = pack_service.build_pack(
            branch_id='branch-pack',
            chapter_index=2,
            query_text='古符异动突然兑现',
            signal_type='foreshadow',
            limit=3,
        )
        assert pack.semantic_hits
        assert pack.latest_signals
        assert pack.clusters
        assert 'payoff_of' in pack.link_types
        assert any('古符异动伏笔' in item for item in pack.support_texts)
        assert any(item.startswith('第1章') or item.startswith('cluster:') for item in pack.support_texts)
        assert isinstance(pack.graph_paths, list)
        assert isinstance(pack.state_summaries, list)
        assert isinstance(pack.exact_hints, list)
        assert isinstance(pack.exact_contexts, list)


def test_risk_evidence_pack_service_falls_back_to_support_texts_for_state_summaries() -> None:
    with _session() as session:
        store = RiskSignalStoreService(session)
        store.embedding_provider = DeterministicStubEmbeddingProvider(dim=8)
        links = RiskSignalLinkService(session)
        store.replace_branch_chapter_signals(
            branch_id='branch-pack-2',
            chapter_index=1,
            items=[
                {
                    'signal_type': 'relationship',
                    'source_field': 'state_summary.evolved_relations',
                    'raw_text': '卫图与族兄关系缓和',
                    'canonical_label': '关系缓和',
                    'canonical_group': 'relationship',
                    'confidence': 0.6,
                }
            ],
        )
        clusters = RiskSignalClusterService(session)
        pack_service = RiskEvidencePackService(session, store, links, clusters)
        pack = pack_service.build_pack(
            branch_id='branch-pack-2',
            chapter_index=2,
            query_text='卫图和族兄关系突然缓和',
            signal_type='relationship',
            limit=3,
        )
        assert pack.support_texts
        assert pack.state_summaries


def test_risk_evidence_pack_service_collects_exact_fact_hints() -> None:
    with _session() as session:
        session.add(
            FactRecord(
                branch_id='branch-pack-3',
                chapter_index=1,
                fact_type='world_rule',
                label='外城访客不得直接调动全城阵法',
                evidence_list=['规则说明'],
                confidence=0.8,
            )
        )
        session.commit()
        store = RiskSignalStoreService(session)
        store.embedding_provider = DeterministicStubEmbeddingProvider(dim=8)
        links = RiskSignalLinkService(session)
        clusters = RiskSignalClusterService(session)
        pack_service = RiskEvidencePackService(session, store, links, clusters)
        pack = pack_service.build_pack(
            branch_id='branch-pack-3',
            chapter_index=2,
            query_text='外城访客不得直接调动全城阵法',
            signal_type='rule_scope',
            limit=3,
        )
        assert any(item.startswith('fact:world_rule:') for item in pack.exact_hints)
        assert pack.exact_contexts
        assert any(item.startswith('exact:world_rule:第1章:') for item in pack.support_texts)


def test_risk_evidence_pack_service_collects_latest_object_labels_into_support_texts(tmp_path) -> None:
    from novel_analyzer.database.models import ChapterArtifact
    from novel_analyzer.services.graph_service import GraphService
    from novel_analyzer.services.ingest_service import IngestService
    from novel_analyzer.services.run_service import RunService

    with _session() as session:
        novel_path = tmp_path / 'novel.txt'
        novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '前文基线',
                'chapter_summary': '前文已有关系与规则。',
                'key_entities': ['卫图'],
                'key_events': ['关系与规则变化'],
                'state_summary': {
                    'evolved_relations': ['卫图与族兄关系缓和'],
                    'constraining_world_rules': ['外城访客不得直接调动全城阵法'],
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
        store = RiskSignalStoreService(session)
        store.embedding_provider = DeterministicStubEmbeddingProvider(dim=8)
        links = RiskSignalLinkService(session)
        clusters = RiskSignalClusterService(session)
        pack_service = RiskEvidencePackService(session, store, links, clusters)
        pack = pack_service.build_pack(
            branch_id=branch.id,
            chapter_index=2,
            query_text='外城访客不得直接调动全城阵法',
            signal_type='rule_scope',
            limit=3,
        )
        assert any(item.startswith('object:') for item in pack.support_texts)
