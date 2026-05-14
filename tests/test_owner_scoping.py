from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novel_analyzer.database.base import Base
from novel_analyzer.database.models import (
    AnalysisRun,
    ChapterManifest,
    NovelSource,
    RunBranch,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def test_owner_user_id_default_is_local_default(session):
    ns = NovelSource(title="t", source_path="/x", source_hash="h1")
    session.add(ns)
    session.commit()
    assert ns.owner_user_id == "local-default"


def test_run_owner_user_id_default(session):
    ns = NovelSource(title="t", source_path="/x", source_hash="h1")
    session.add(ns)
    session.flush()
    cm = ChapterManifest(novel_id=ns.id, version=1, splitter_version="v1", chapter_count=10)
    session.add(cm)
    session.flush()
    run = AnalysisRun(
        novel_id=ns.id,
        manifest_id=cm.id,
        llm_base_url="http://x",
        llm_model_name="m",
    )
    session.add(run)
    session.commit()
    assert run.owner_user_id == "local-default"


def test_branch_owner_user_id_default(session):
    ns = NovelSource(title="t", source_path="/x", source_hash="h1")
    session.add(ns)
    session.flush()
    cm = ChapterManifest(novel_id=ns.id, version=1, splitter_version="v1", chapter_count=10)
    session.add(cm)
    session.flush()
    run = AnalysisRun(
        novel_id=ns.id,
        manifest_id=cm.id,
        llm_base_url="http://x",
        llm_model_name="m",
    )
    session.add(run)
    session.flush()
    branch = RunBranch(run_id=run.id, name="main")
    session.add(branch)
    session.commit()
    assert branch.owner_user_id == "local-default"


def test_two_users_isolated(session):
    ns_a = NovelSource(title="alice book", source_path="/a", source_hash="ha", owner_user_id="alice")
    ns_b = NovelSource(title="bob book", source_path="/b", source_hash="hb", owner_user_id="bob")
    session.add_all([ns_a, ns_b])
    session.commit()

    alice_books = session.query(NovelSource).filter(NovelSource.owner_user_id == "alice").all()
    bob_books = session.query(NovelSource).filter(NovelSource.owner_user_id == "bob").all()

    assert len(alice_books) == 1
    assert len(bob_books) == 1
    assert alice_books[0].title == "alice book"
    assert bob_books[0].title == "bob book"


def test_owner_user_id_indexed(session):
    bind = session.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)
    indexes = inspector.get_indexes("novel_sources")
    assert any("owner_user_id" in idx["column_names"] for idx in indexes), \
        "owner_user_id should be indexed on novel_sources"
