import json
from io import BytesIO
from types import TracebackType
from typing import Any, cast
from wsgiref.types import StartResponse

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.app.main import application
from novel_analyzer.database.session import create_schema
from novel_analyzer.services.cluster_review_service import ClusterReviewService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.risk_audit_service import RiskAuditService
from novel_analyzer.services.run_service import RunService


def _call(path: str) -> tuple[str, bytes]:
    captured: dict[str, Any] = {}
    path_info, _, query = path.partition("?")

    def start_response(
        status: str,
        headers: list[tuple[str, str]],
        exc_info: tuple[type[BaseException], BaseException, TracebackType]
        | tuple[None, None, None]
        | None = None,
    ) -> object:
        _ = exc_info
        captured["status"] = status
        captured["headers"] = headers
        return lambda chunk: None

    start = cast(StartResponse, start_response)
    body = b"".join(
        application(
            {
                "REQUEST_METHOD": "GET",
                "PATH_INFO": path_info,
                "QUERY_STRING": query,
                "wsgi.input": BytesIO(),
            },
            start,
        )
    )
    return captured["status"], body


def _call_post_json(path: str, payload: dict[str, object]) -> tuple[str, bytes]:
    captured: dict[str, Any] = {}

    def start_response(
        status: str,
        headers: list[tuple[str, str]],
        exc_info: tuple[type[BaseException], BaseException, TracebackType]
        | tuple[None, None, None]
        | None = None,
    ) -> object:
        _ = exc_info
        captured["status"] = status
        captured["headers"] = headers
        return lambda chunk: None

    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    body = b"".join(
        application(
            {
                "REQUEST_METHOD": "POST",
                "PATH_INFO": path,
                "CONTENT_TYPE": "application/json",
                "CONTENT_LENGTH": str(len(raw)),
                "QUERY_STRING": "",
                "wsgi.input": BytesIO(raw),
            },
            cast(StartResponse, start_response),
        )
    )
    return captured["status"], body


def test_health_endpoint_returns_ok() -> None:
    status, body = _call("/health")
    assert status == "200 OK"
    assert b'"status": "ok"' in body


def test_meta_endpoint_lists_available_routes() -> None:
    status, body = _call("/api/meta")
    assert status == "200 OK"
    assert b"/api/mock/import" in body


def test_mock_import_endpoint_uses_profile_query() -> None:
    status, body = _call("/api/mock/import?profile=manual")
    assert status == "200 OK"
    assert b'"pipeline_profile": "manual"' in body


def test_run_snapshot_requires_query_params() -> None:
    status, body = _call("/api/run-snapshot")
    assert status == "400 Bad Request"
    assert b"missing query parameter" in body


def test_chapter_bundle_requires_query_params() -> None:
    status, body = _call("/api/chapter-bundle")
    assert status == "400 Bad Request"
    assert b"missing query parameter" in body


def test_chapter_qa_context_requires_query_params() -> None:
    status, body = _call("/api/chapter-qa-context")
    assert status == "400 Bad Request"
    assert b"missing query parameter" in body


def test_import_endpoint_requires_uploaded_file() -> None:
    captured: dict[str, Any] = {}

    def start_response(
        status: str,
        headers: list[tuple[str, str]],
        exc_info: tuple[type[BaseException], BaseException, TracebackType]
        | tuple[None, None, None]
        | None = None,
    ) -> object:
        _ = exc_info
        captured["status"] = status
        captured["headers"] = headers
        return lambda chunk: None

    body = b"".join(
        application(
            {
                "REQUEST_METHOD": "POST",
                "PATH_INFO": "/api/import",
                "CONTENT_TYPE": "multipart/form-data; boundary=test",
                "CONTENT_LENGTH": "0",
                "QUERY_STRING": "",
                "wsgi.input": BytesIO(),
            },
            cast(StartResponse, start_response),
        )
    )
    assert captured["status"] == "400 Bad Request"
    assert b"missing uploaded file" in body


def test_recovery_endpoint_requires_action_fields() -> None:
    captured: dict[str, Any] = {}

    def start_response(
        status: str,
        headers: list[tuple[str, str]],
        exc_info: tuple[type[BaseException], BaseException, TracebackType]
        | tuple[None, None, None]
        | None = None,
    ) -> object:
        _ = exc_info
        captured["status"] = status
        captured["headers"] = headers
        return lambda chunk: None

    payload = b"{}"
    body = b"".join(
        application(
            {
                "REQUEST_METHOD": "POST",
                "PATH_INFO": "/api/recovery",
                "CONTENT_TYPE": "application/json",
                "CONTENT_LENGTH": str(len(payload)),
                "QUERY_STRING": "",
                "wsgi.input": BytesIO(payload),
            },
            cast(StartResponse, start_response),
        )
    )
    assert captured["status"] == "400 Bad Request"
    assert b"run_id, branch_id and action are required" in body


def test_review_cluster_endpoints_round_trip(monkeypatch, tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr("apps.api.app.main.create_session_factory", lambda settings=None: factory)

    with factory() as session:
        novel_path = tmp_path / "novel.txt"
        novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        run_id = run.id
        branch_id = branch.id
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                "chapter_index": 1,
                "normalized_title": "命格初现",
                "chapter_summary": "卫图在本章做出异常决定。",
                "key_entities": ["卫图"],
                "key_events": ["卫图做出异常决定"],
                "continuity_notes": ["主线推进。"],
                "ooc_candidates": [
                    {
                        "character_name": "卫图",
                        "risk_type": "motivation_shift",
                        "severity": "medium",
                        "summary": "卫图目标改变过快。",
                        "supporting_evidence": ["前文目标A"],
                        "counter_evidence": ["也许有新情报"],
                    }
                ],
                "needs_human_review": True,
                "dimensions": [],
            },
        )
        RiskAuditService(session).generate_for_chapter(branch.id, 1)

    status, body = _call(f"/api/review-clusters?run_id={run_id}&branch_id={branch_id}")
    assert status == "200 OK"
    assert b'"items"' in body
    assert b'"contract_version": "review-workflow.v1"' in body
    assert b'"allowed_cluster_statuses"' in body
    assert b'"review_storage_mode"' in body
    assert b'"stable_contract_version": "review-api-pre-v1"' in body

    cluster_key = "character_ooc|::|motivation_shift"
    status, body = _call_post_json(
        "/api/review-cluster-update",
        {
            "branch_id": branch_id,
            "cluster_key": cluster_key,
            "cluster_status": "reviewed",
            "review_result": "confirmed-benign",
            "review_notes": "api test",
            "review_owner": "editor-a",
        },
    )
    assert status == "200 OK"
    assert b'"cluster_status": "reviewed"' in body
    assert b'"stable_contract_version": "review-api-pre-v1"' in body

    status, body = _call(
        f"/api/review-cluster-history?branch_id={branch_id}&cluster_key={cluster_key}"
    )
    assert status == "200 OK"
    assert b'"previous_cluster_status"' in body
    assert b'"event_type": "status_update"' in body
    assert b'"event_index": 1' in body
    assert b'"audit_key"' in body
    assert b'"previous_values"' in body
    assert b'"current_values"' in body
    assert b'"changed_fields"' in body
    assert b'"transition": "new->reviewed"' in body


def test_review_cluster_history_endpoint_handles_unmigrated_review_tables(monkeypatch) -> None:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr("apps.api.app.main.create_session_factory", lambda settings=None: factory)

    status, body = _call("/api/review-cluster-history?branch_id=branch-x&cluster_key=cluster-y")

    assert status == "200 OK"
    assert b'"review_storage_mode": "file-fallback"' in body
    assert b'"items": []' in body


def test_review_clusters_endpoint_supports_filters(monkeypatch, tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr("apps.api.app.main.create_session_factory", lambda settings=None: factory)

    with factory() as session:
        novel_path = tmp_path / "novel.txt"
        novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        run_id = run.id
        branch_id = branch.id
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                "chapter_index": 1,
                "normalized_title": "命格初现",
                "chapter_summary": "卫图在本章做出异常决定。",
                "key_entities": ["卫图"],
                "key_events": ["卫图做出异常决定"],
                "continuity_notes": ["主线推进。"],
                "ooc_candidates": [
                    {
                        "character_name": "卫图",
                        "risk_type": "motivation_shift",
                        "severity": "medium",
                        "summary": "卫图目标改变过快。",
                        "supporting_evidence": ["前文目标A"],
                        "counter_evidence": ["也许有新情报"],
                    }
                ],
                "needs_human_review": True,
                "dimensions": [],
            },
        )
        RiskAuditService(session).generate_for_chapter(branch.id, 1)
        ClusterReviewService(session).write(
            branch_id=branch.id,
            cluster_key="character_ooc|::|motivation_shift",
            cluster_status="reviewed",
            review_result="confirmed-benign",
            review_notes="api filter test",
            review_owner="editor-a",
        )

    status, body = _call(
        f"/api/review-clusters?run_id={run_id}&branch_id={branch_id}&cluster_status=reviewed&review_owner=editor-a&review_result=confirmed-benign"
    )
    assert status == "200 OK"
    assert b'"items"' in body
    assert b'"filters"' in body
    assert b'"review_owner": "editor-a"' in body


def test_review_cluster_summary_endpoint_returns_aggregates(monkeypatch, tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr("apps.api.app.main.create_session_factory", lambda settings=None: factory)

    with factory() as session:
        novel_path = tmp_path / "novel.txt"
        novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        run_id = run.id
        branch_id = branch.id
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                "chapter_index": 1,
                "normalized_title": "命格初现",
                "chapter_summary": "卫图在本章做出异常决定。",
                "key_entities": ["卫图"],
                "key_events": ["卫图做出异常决定"],
                "continuity_notes": ["主线推进。"],
                "ooc_candidates": [
                    {
                        "character_name": "卫图",
                        "risk_type": "motivation_shift",
                        "severity": "medium",
                        "summary": "卫图目标改变过快。",
                        "supporting_evidence": ["前文目标A"],
                        "counter_evidence": ["也许有新情报"],
                    }
                ],
                "needs_human_review": True,
                "dimensions": [],
            },
        )
        RiskAuditService(session).generate_for_chapter(branch.id, 1)
        ClusterReviewService(session).write(
            branch_id=branch.id,
            cluster_key="character_ooc|::|motivation_shift",
            cluster_status="reviewed",
            review_result="confirmed-benign",
            review_notes="api summary test",
            review_owner="editor-a",
        )

    status, body = _call(f"/api/review-cluster-summary?run_id={run_id}&branch_id={branch_id}")
    assert status == "200 OK"
    assert b'"contract_version": "review-workflow.v1"' in body
    assert b'"cluster_count": 1' in body
    assert b'"history_event_count": 1' in body
    assert b'"stable_contract_version": "review-api-pre-v1"' in body
    assert b'"latest_review_owner": "editor-a"' in body
    assert b'"latest_review_result": "confirmed-benign"' in body
    assert '"latest_review_result_label": "确认无问题"'.encode("utf-8") in body
    assert b'"P2": 1' in body
    assert '"单点问题": 1'.encode("utf-8") in body
    assert b'"reviewed": 1' in body
    assert b'"confirmed-benign": 1' in body
    assert b'"editor-a": 1' in body


def test_review_cluster_summary_endpoint_supports_filters(monkeypatch, tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr("apps.api.app.main.create_session_factory", lambda settings=None: factory)

    with factory() as session:
        novel_path = tmp_path / "novel.txt"
        novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        run_id = run.id
        branch_id = branch.id
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                "chapter_index": 1,
                "normalized_title": "命格初现",
                "chapter_summary": "卫图在本章做出异常决定。",
                "key_entities": ["卫图"],
                "key_events": ["卫图做出异常决定"],
                "continuity_notes": ["主线推进。"],
                "ooc_candidates": [
                    {
                        "character_name": "卫图",
                        "risk_type": "motivation_shift",
                        "severity": "medium",
                        "summary": "卫图目标改变过快。",
                        "supporting_evidence": ["前文目标A"],
                        "counter_evidence": ["也许有新情报"],
                    }
                ],
                "needs_human_review": True,
                "dimensions": [],
            },
        )
        RiskAuditService(session).generate_for_chapter(branch.id, 1)
        ClusterReviewService(session).write(
            branch_id=branch.id,
            cluster_key="character_ooc|::|motivation_shift",
            cluster_status="reviewed",
            review_result="confirmed-benign",
            review_notes="api summary filter test",
            review_owner="editor-a",
        )

    status, body = _call(
        f"/api/review-cluster-summary?run_id={run_id}&branch_id={branch_id}"
        f"&cluster_status=reviewed&review_owner=editor-a&review_result=confirmed-benign"
    )
    assert status == "200 OK"
    assert b'"cluster_count": 1' in body
    assert b'"confirmed-benign": 1' in body


def test_review_cluster_update_returns_400_for_invalid_status_combo(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr("apps.api.app.main.create_session_factory", lambda settings=None: factory)

    status, body = _call_post_json(
        "/api/review-cluster-update",
        {
            "branch_id": "branch-x",
            "cluster_key": "cluster-y",
            "cluster_status": "resolved",
            "review_result": "",
        },
    )
    assert status == "400 Bad Request"
    assert b"requires a non-empty review_result" in body
