from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novel_analyzer.database.models import FactRecord
from novel_analyzer.database.session import create_schema
from novel_analyzer.services.risk_exact_context_service import RiskExactContextService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def test_risk_exact_context_service_returns_latest_fact_hits() -> None:
    with _session() as session:
        session.add_all(
            [
                FactRecord(branch_id='branch-exact', chapter_index=1, fact_type='world_rule', label='外城访客不得直接调动全城阵法', evidence_list=['规则说明'], confidence=0.8),
                FactRecord(branch_id='branch-exact', chapter_index=2, fact_type='world_rule', label='外城访客不得直接调动全城阵法（旧案）', evidence_list=['规则说明'], confidence=0.7),
            ]
        )
        session.commit()
        service = RiskExactContextService(session)
        hits = service.latest_fact_hits(
            branch_id='branch-exact',
            query_text='外城访客不得直接调动全城阵法',
            before_chapter_index=3,
            limit=5,
        )
        assert hits
        assert hits[0].chapter_index == 2
