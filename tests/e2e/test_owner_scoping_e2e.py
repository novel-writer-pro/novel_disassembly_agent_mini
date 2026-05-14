"""Reader v3/v4 owner scoping — FastAPI surface (post-v5 cutover).

Tests that the v3 IdentityMiddleware + library router correctly scope
results by X-User-Id header.

Strategy: patch the get_db_session helper in apps.api.app.routers to
return a SQLite session pre-loaded with two users (alice and bob).
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.app.fastapi_app import create_app
from novel_analyzer.database.base import Base
from novel_analyzer.database.models import (
    AnalysisRun,
    ChapterManifest,
    NovelSource,
    RunBranch,
)


@pytest.fixture
def factory(tmp_path):
    db_file = tmp_path / "scoping_e2e.sqlite"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        for owner in ("alice", "bob"):
            novel = NovelSource(
                title=f"{owner}-book",
                source_path=f"/tmp/{owner}.txt",
                source_hash=owner * 8,
                metadata_json={},
                owner_user_id=owner,
            )
            session.add(novel)
            session.flush()
            manifest = ChapterManifest(
                novel_id=novel.id,
                version=1,
                splitter_version="v1",
                chapter_count=1,
                notes={},
            )
            session.add(manifest)
            session.flush()
            run = AnalysisRun(
                novel_id=novel.id,
                manifest_id=manifest.id,
                llm_base_url="http://test",
                llm_model_name="m",
                analysis_profile={},
                owner_user_id=owner,
            )
            session.add(run)
            session.flush()
            branch = RunBranch(
                run_id=run.id,
                name="main",
                fork_after_chapter_index=0,
                status="active",
                owner_user_id=owner,
            )
            session.add(branch)
        session.commit()
    return Session


@pytest.fixture
def client(monkeypatch, factory):
    """FastAPI client with get_db_session patched to use SQLite test factory."""

    Session = factory

    @contextmanager
    def fake_get_db_session(database_url: str | None = None):
        s = Session()
        try:
            yield s
        finally:
            s.close()

    import apps.api.app.routers as routers_pkg
    monkeypatch.setattr(routers_pkg, "get_db_session", fake_get_db_session)
    # The library router imports the helper at import time; patch on the module too.
    import apps.api.app.routers.library as library_module
    monkeypatch.setattr(library_module, "get_db_session", fake_get_db_session)

    return TestClient(create_app())


def _titles(payload: dict[str, Any]) -> set[str]:
    return {item["title"] for item in payload.get("items", [])}


def test_alice_sees_only_alice(client):
    r = client.get("/api/library", headers={"X-User-Id": "alice"})
    assert r.status_code == 200
    assert _titles(r.json()) == {"alice-book"}


def test_bob_sees_only_bob(client):
    r = client.get("/api/library", headers={"X-User-Id": "bob"})
    assert r.status_code == 200
    assert _titles(r.json()) == {"bob-book"}


def test_no_header_sees_all(client):
    """No X-User-Id header → user_id defaults to "local-default" → no filter."""
    r = client.get("/api/library")
    assert r.status_code == 200
    assert _titles(r.json()) == {"alice-book", "bob-book"}


def test_empty_header_falls_back_to_all(client):
    """Empty/whitespace X-User-Id is normalized to local-default → no filter."""
    r = client.get("/api/library", headers={"X-User-Id": "  "})
    assert r.status_code == 200
    assert _titles(r.json()) == {"alice-book", "bob-book"}


def test_unknown_user_returns_empty(client):
    r = client.get("/api/library", headers={"X-User-Id": "carol"})
    assert r.status_code == 200
    assert _titles(r.json()) == set()
