from __future__ import annotations

import json
from io import BytesIO
from typing import Any, cast
from wsgiref.types import StartResponse

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import apps.api.app.main as api_main
from apps.api.app.main import application
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


def _wsgi_call(path: str, headers: dict[str, str] | None = None) -> tuple[str, dict[str, Any]]:
    captured: dict[str, Any] = {}
    path_info, _, query = path.partition("?")

    def start_response(status: str, headers_list: list, exc_info=None) -> object:
        captured["status"] = status
        return lambda chunk: None

    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path_info,
        "QUERY_STRING": query,
        "wsgi.input": BytesIO(),
    }
    for k, v in (headers or {}).items():
        environ[f"HTTP_{k.upper().replace('-', '_')}"] = v

    raw = b"".join(application(environ, cast(StartResponse, start_response)))
    return captured["status"], json.loads(raw)


@pytest.fixture
def patched_library(monkeypatch, factory):
    """Replace _library_payload's session-factory call with our SQLite factory."""

    real_payload = api_main._library_payload
    Session = factory

    def fake_payload(database_url, limit, owner_user_id=None):
        rows: list[dict[str, Any]] = []
        with Session() as session:
            query = session.query(RunBranch)
            if owner_user_id is not None:
                query = query.filter(RunBranch.owner_user_id == owner_user_id)
            branches = query.order_by(RunBranch.updated_at.desc()).limit(limit).all()
            for branch in branches:
                run = session.get(AnalysisRun, branch.run_id)
                if run is None:
                    continue
                novel = session.get(NovelSource, run.novel_id)
                if novel is None:
                    continue
                rows.append(
                    {
                        "novel_id": novel.id,
                        "title": novel.title,
                        "run_id": run.id,
                        "branch_id": branch.id,
                        "branch_name": branch.name,
                        "owner_user_id": branch.owner_user_id,
                    }
                )
        return {"items": rows}

    monkeypatch.setattr(api_main, "_library_payload", fake_payload)
    yield


def test_wsgi_library_alice_sees_only_alice(patched_library):
    status, payload = _wsgi_call("/api/library", headers={"X-User-Id": "alice"})
    assert status == "200 OK"
    titles = {item["title"] for item in payload["items"]}
    assert titles == {"alice-book"}


def test_wsgi_library_bob_sees_only_bob(patched_library):
    status, payload = _wsgi_call("/api/library", headers={"X-User-Id": "bob"})
    assert status == "200 OK"
    titles = {item["title"] for item in payload["items"]}
    assert titles == {"bob-book"}


def test_wsgi_library_no_header_sees_all(patched_library):
    status, payload = _wsgi_call("/api/library")
    assert status == "200 OK"
    titles = {item["title"] for item in payload["items"]}
    assert titles == {"alice-book", "bob-book"}


def test_wsgi_library_empty_header_falls_back_to_all(patched_library):
    status, payload = _wsgi_call("/api/library", headers={"X-User-Id": "  "})
    assert status == "200 OK"
    titles = {item["title"] for item in payload["items"]}
    assert titles == {"alice-book", "bob-book"}


def test_wsgi_library_unknown_user_returns_empty(patched_library):
    status, payload = _wsgi_call("/api/library", headers={"X-User-Id": "carol"})
    assert status == "200 OK"
    assert payload["items"] == []
