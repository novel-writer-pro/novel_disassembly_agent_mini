import json
import re
from pathlib import Path
from io import BytesIO
from types import TracebackType
from typing import Any, cast
from wsgiref.types import StartResponse

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from apps.api.app.main import _API_ENDPOINT_SPECS, application
from novel_analyzer.application.dto import AutoRunResult, BranchSnapshot, RunSnapshot
from novel_analyzer.config.settings import get_settings
from novel_analyzer.database.session import create_schema
from novel_analyzer.runtime.cluster_review_state import (
    read_cluster_review_state,
    write_cluster_review_state,
)
from novel_analyzer.services.cluster_review_service import (
    ClusterReviewService,
    ClusterReviewStorageUnavailable,
)
from novel_analyzer.services.export_service import ExportService
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
    assert b"/api/import" in body
    assert b"/api/start" in body
    assert b"/api/recovery" in body
    assert b"available_endpoint_specs" in body
    assert b'"method": "POST"' in body
    assert b"Current backend is dependency-light WSGI JSON." in body
    assert b"future work" not in body

    payload = json.loads(body)
    meta_paths = sorted(item["path"] for item in payload["available_endpoint_specs"])
    assert sorted(item["path"] for item in _API_ENDPOINT_SPECS) == meta_paths

    normalized_meta_pairs = sorted((item["path"], item["method"]) for item in payload["available_endpoint_specs"])
    expected_pairs = sorted((item["path"], item["method"]) for item in _API_ENDPOINT_SPECS)
    assert expected_pairs == normalized_meta_pairs


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


def test_root_readme_points_to_current_api_surface_doc() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "docs/api-current-surface.md" in readme


def test_root_readme_heading_levels_do_not_jump() -> None:
    import re

    levels: list[int] = []
    for line in Path("README.md").read_text(encoding="utf-8").splitlines():
        match = re.match(r'^(#{1,6})\s+', line)
        if match:
            levels.append(len(match.group(1)))

    prev = None
    for level in levels:
        if prev is not None:
            assert level <= prev + 1
        prev = level


def test_api_contract_doc_points_back_to_current_surface() -> None:
    text = Path("docs/api-contract.md").read_text(encoding="utf-8")
    assert "docs/api-current-surface.md" in text


def test_api_contract_markdown_fences_are_balanced() -> None:
    text = Path("docs/api-contract.md").read_text(encoding="utf-8")
    assert text.count("```") % 2 == 0


def test_docs_readme_numbered_sections_are_sequential() -> None:
    import re

    text = Path("docs/README.md").read_text(encoding="utf-8")
    for match in re.finditer(r'^###\s+(.+)$', text, re.M):
        start = match.start()
        next_m = re.search(r'^###\s+.+$', text[match.end():], re.M)
        end = match.end() + next_m.start() if next_m else len(text)
        chunk = text[start:end]
        nums = [int(m.group(1)) for m in re.finditer(r'^(\d+)\. ', chunk, re.M)]
        if nums:
            assert nums == list(range(1, len(nums) + 1))


def test_maintainer_and_risk_audit_docs_point_to_current_api_surface_doc() -> None:
    checks = {
        "docs/roles/maintainer/README.md": "api-current-surface.md",
        "docs/tracks/risk-audit/README.md": "api-current-surface.md",
    }
    for path, needle in checks.items():
        text = Path(path).read_text(encoding="utf-8")
        assert needle in text


def test_non_technical_docs_do_not_point_to_current_api_surface_doc() -> None:
    checks = [
        "docs/roles/product/README.md",
        "docs/tracks/reader-experience/README.md",
    ]
    for path in checks:
        text = Path(path).read_text(encoding="utf-8")
        assert "api-current-surface.md" not in text


def test_roles_and_tracks_index_point_to_current_api_surface_doc() -> None:
    checks = {
        "docs/roles/README.md": "api-current-surface.md",
        "docs/tracks/README.md": "api-current-surface.md",
    }
    for path, needle in checks.items():
        text = Path(path).read_text(encoding="utf-8")
        assert needle in text


def test_role_and_track_docs_point_to_current_api_surface_doc() -> None:
    checks = {
        "docs/roles/integrator/README.md": "api-current-surface.md",
        "docs/roles/backend/README.md": "api-current-surface.md",
        "docs/tracks/review-workflow/README.md": "api-current-surface.md",
    }
    for path, needle in checks.items():
        text = Path(path).read_text(encoding="utf-8")
        assert needle in text


def test_docs_readme_developer_flow_mentions_current_api_surface_third() -> None:
    text = Path("docs/README.md").read_text(encoding="utf-8")
    assert "3. [`./api-current-surface.md`](./api-current-surface.md)" in text
    assert "第 3 步：再看当前已实现 API surface" in text


def test_docs_readme_integrator_flow_mentions_current_api_surface_second() -> None:
    text = Path("docs/README.md").read_text(encoding="utf-8")
    assert "第 2 步：再看当前已实现 API surface" in text


def test_docs_readme_points_to_current_api_surface_doc() -> None:
    readme = Path("docs/README.md").read_text(encoding="utf-8")
    assert "./api-current-surface.md" in readme


def test_risk_audit_indexes_point_to_production_readiness_doc() -> None:
    checks = {
        "docs/README.md": "./risk-audit-production-readiness.md",
        "docs/risk-audit-docs-index.md": "./risk-audit-production-readiness.md",
        "docs/architecture/README.md": "../risk-audit-production-readiness.md",
    }
    for path, needle in checks.items():
        text = Path(path).read_text(encoding="utf-8")
        assert needle in text


def test_docs_readme_sample_novel_chain_includes_first_10_risk_report() -> None:
    text = Path("docs/README.md").read_text(encoding="utf-8")
    assert "../.omx/reports/sample-novel-first-10-risk-check-20260502.md" in text


def test_alembic_cluster_review_revisions_are_linearized() -> None:
    records = Path("alembic/versions/20260430_01_cluster_review_records.py").read_text(
        encoding="utf-8"
    )
    bridge = Path("alembic/versions/20260429_01_cluster_review_tables.py").read_text(
        encoding="utf-8"
    )
    tables = Path("alembic/versions/20260430_01_cluster_review_tables.py").read_text(
        encoding="utf-8"
    )
    assert "revision = '20260430_02'" in records
    assert "down_revision = '20260430_01'" in records
    assert 'revision = "20260429_01"' in bridge
    assert "revision = '20260430_01'" in tables
    assert "down_revision = '20260429_01'" in tables


def test_api_current_surface_doc_matches_route_inventory() -> None:
    source = Path("apps/api/app/main.py").read_text(encoding="utf-8")
    route_paths = sorted(set(re.findall(r'path == "([^"]+)"', source)))

    current_doc = Path("docs/api-current-surface.md").read_text(encoding="utf-8")
    mentioned = sorted(
        set(
            match.group(1)
            for match in re.finditer(r'`(?:GET|POST) (/[^` ?]+)', current_doc)
        )
    )

    assert route_paths == mentioned


def test_api_current_surface_doc_mentions_endpoint_specs_source_of_truth() -> None:
    text = Path("docs/api-current-surface.md").read_text(encoding="utf-8")
    assert "_API_ENDPOINT_SPECS" in text
    assert "available_endpoint_specs" in text
    assert "available_endpoints" in text


def test_api_endpoint_specs_have_unique_paths() -> None:
    paths = [item["path"] for item in _API_ENDPOINT_SPECS]
    assert len(paths) == len(set(paths))


def test_api_current_surface_doc_points_to_target_contract() -> None:
    text = Path("docs/api-current-surface.md").read_text(encoding="utf-8")
    assert "docs/api-contract.md" in text
    assert "未来目标契约" in text


def test_api_readme_route_inventory_matches_implemented_routes() -> None:
    source = Path("apps/api/app/main.py").read_text(encoding="utf-8")
    route_paths = sorted(set(re.findall(r'path == "([^"]+)"', source)))

    readme = Path("apps/api/README.md").read_text(encoding="utf-8")
    mentioned = sorted(
        set(
            match.group(1)
            for match in re.finditer(r'`(?:GET|POST) (/[^` ?]+)', readme)
        )
    )

    assert route_paths == mentioned


def test_api_readme_points_to_current_api_surface_doc() -> None:
    readme = Path("apps/api/README.md").read_text(encoding="utf-8")
    assert "docs/api-current-surface.md" in readme
    assert "docs/api-contract.md" in readme


def test_api_readme_mentions_method_aware_meta_specs() -> None:
    readme = Path("apps/api/README.md").read_text(encoding="utf-8")
    assert "available_endpoint_specs" in readme


def test_api_readme_mentions_review_and_search_endpoints() -> None:
    readme = Path("apps/api/README.md").read_text(encoding="utf-8")
    for needle in [
        "`GET /api/review-clusters?run_id=...&branch_id=...`",
        "`GET /api/review-cluster-summary?run_id=...&branch_id=...`",
        "`POST /api/review-batch-execute`",
        "`POST /api/search-branch`",
        "`POST /api/ask-branch`",
        "`GET /api/job-events?branch_id=...&limit=100`",
    ]:
        assert needle in readme


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


def test_import_endpoint_accepts_multipart_upload(monkeypatch, tmp_path) -> None:
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

    def fake_ingest_and_start_pipeline(**kwargs: Any):
        captured["ingest_kwargs"] = kwargs
        return AutoRunResult(
            novel_id="novel-1",
            manifest_id="manifest-1",
            run_id="run-1",
            branch_id="branch-1",
            chapter_count=1,
            processed_chapters=0,
            next_chapter=1,
            pipeline_profile=kwargs.get("pipeline_profile", "manual"),
            pipeline_state="ready",
        )

    monkeypatch.setattr("apps.api.app.main.ingest_and_start_pipeline", fake_ingest_and_start_pipeline)
    monkeypatch.setattr(
        "apps.api.app.main.get_run_snapshot",
        lambda *args, **kwargs: RunSnapshot(
            run_id="run-1",
            branch_id="branch-1",
            branch_name="main",
            pipeline_state="ready",
            manifest_chapter_count=1,
            completed_chapters=0,
            failed_jobs=0,
            running_jobs=0,
            next_chapter=1,
            allowed_actions=["resume"],
        ),
    )
    monkeypatch.setattr(
        "apps.api.app.main.get_branch_snapshot",
        lambda *args, **kwargs: BranchSnapshot(
            branch_id="branch-1",
            pipeline_state="ready",
            allowed_actions=["resume"],
            chapter_rows=[],
            failed_summary=[],
            risk_summary={},
        ),
    )

    boundary = "test-boundary"
    raw = (
        "--test-boundary\r\n"
        'Content-Disposition: form-data; name="title"\r\n\r\n'
        "Sample Title\r\n"
        "--test-boundary\r\n"
        'Content-Disposition: form-data; name="pipeline_profile"\r\n\r\n'
        "manual\r\n"
        "--test-boundary\r\n"
        'Content-Disposition: form-data; name="file"; filename="sample.txt"\r\n'
        "Content-Type: text/plain\r\n\r\n"
        "第1章 一\n正文\n"
        "\r\n--test-boundary--\r\n"
    ).encode("utf-8")

    body = b"".join(
        application(
            {
                "REQUEST_METHOD": "POST",
                "PATH_INFO": "/api/import",
                "CONTENT_TYPE": f"multipart/form-data; boundary={boundary}",
                "CONTENT_LENGTH": str(len(raw)),
                "QUERY_STRING": "",
                "wsgi.input": BytesIO(raw),
            },
            cast(StartResponse, start_response),
        )
    )

    assert captured["status"] == "200 OK"
    assert b'"import_result"' in body
    assert b'"run_snapshot"' in body
    assert b'"branch_snapshot"' in body
    ingest_kwargs = captured["ingest_kwargs"]
    assert ingest_kwargs["title"] == "Sample Title"
    assert ingest_kwargs["pipeline_profile"] == "manual"
    assert Path(ingest_kwargs["path"]).exists()
    assert Path(ingest_kwargs["path"]).read_text(encoding="utf-8") == "第1章 一\n正文\n"


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
            "review_actor": "api-bot",
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
    assert b'"event_type": "assignment_update"' in body
    assert b'"event_index": 1' in body
    assert b'"audit_key"' in body
    assert b'"previous_values"' in body
    assert b'"current_values"' in body
    assert b'"changed_fields"' in body
    assert b'"transition": "new->reviewed"' in body
    assert b'"review_actor": "api-bot"' in body


def test_review_cluster_history_endpoint_handles_unmigrated_review_tables(monkeypatch) -> None:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr("apps.api.app.main.create_session_factory", lambda settings=None: factory)

    status, body = _call("/api/review-cluster-history?branch_id=branch-x&cluster_key=cluster-y")

    assert status == "200 OK"
    assert b'"review_storage_mode": "file-fallback"' in body
    assert b'"items": []' in body


def test_review_cluster_history_endpoint_supports_filters(monkeypatch, tmp_path) -> None:
    settings = get_settings().model_copy(deep=True)
    settings.runtime_cache_dir = str(tmp_path / "runtime-cache")
    monkeypatch.setattr("apps.api.app.main.get_settings", lambda: settings)
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr("apps.api.app.main.create_session_factory", lambda settings=None: factory)

    write_cluster_review_state(
        "branch-x",
        "cluster-y",
        "needs_review",
        review_result="deferred",
        review_notes="待处理",
        review_owner="editor-a",
        review_actor="editor-a",
        settings=settings,
    )
    write_cluster_review_state(
        "branch-x",
        "cluster-y",
        "needs_review",
        review_result="deferred",
        review_notes="待处理",
        review_owner="editor-b",
        review_actor="review-bot",
        settings=settings,
    )

    status, body = _call(
        "/api/review-cluster-history?branch_id=branch-x&cluster_key=cluster-y"
        "&event_type=assignment_update&review_owner=editor-b&review_result=deferred&limit=1"
    )
    payload = json.loads(body)
    assert status == "200 OK"
    assert payload["filters"] == {
        "event_type": "assignment_update",
        "review_owner": "editor-b",
        "review_result": "deferred",
    }
    assert len(payload["items"]) == 1
    assert payload["items"][0]["event_type"] == "assignment_update"
    assert payload["items"][0]["review_owner"] == "editor-b"
    assert payload["items"][0]["review_actor"] == "review-bot"


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
        f"/api/review-clusters?run_id={run_id}&branch_id={branch_id}"
        "&cluster_status=reviewed&review_owner=editor-a&review_result=confirmed-benign"
        "&review_priority=P2&pattern_label=%E5%8D%95%E7%82%B9%E9%97%AE%E9%A2%98"
    )
    payload = json.loads(body)
    assert status == "200 OK"
    assert payload["filters"] == {
        "cluster_status": "reviewed",
        "review_owner": "editor-a",
        "review_result": "confirmed-benign",
        "review_priority": "P2",
        "pattern_label": "单点问题",
    }
    assert payload["items"][0]["review_owner"] == "editor-a"


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
            review_actor="review-bot",
        )

    status, body = _call(f"/api/review-cluster-summary?run_id={run_id}&branch_id={branch_id}")
    assert status == "200 OK"
    assert b'"contract_version": "review-workflow.v1"' in body
    assert b'"cluster_count": 1' in body
    assert b'"history_event_count": 1' in body
    assert b'"stable_contract_version": "review-api-pre-v1"' in body
    assert b'"latest_review_owner": "editor-a"' in body
    assert b'"latest_review_actor": "review-bot"' in body
    assert b'"latest_review_event_type": "assignment_update"' in body
    assert b'"latest_review_result": "confirmed-benign"' in body
    assert '"latest_review_result_label": "确认无问题"'.encode() in body
    assert b'"P2": 1' in body
    assert '"单点问题": 1'.encode() in body
    assert b'"reviewed": 1' in body
    assert b'"confirmed-benign": 1' in body
    assert b'"editor-a": 1' in body
    assert b'"review-bot": 1' in body
    assert b'"current_owner_top": "editor-a"' in body
    assert b'"latest_actor_top": "review-bot"' in body
    assert b'"latest_event_type_top": "assignment_update"' in body
    assert b'"workflow_lane_top": "assignment_queue"' in body
    assert b'"queue_priority_top": "high"' in body
    assert b'"deadline_level_top": "soon"' in body
    assert b'"batch_operation_hint_top": "batch_owner_handoff_followup"' in body
    assert b'"escalation_tier_top": ""' in body
    assert b'"auto_next_action_code_top": "notify_owner_to_take_over"' in body
    assert b'"auto_next_action_top":' in body
    assert b'"escalation_reason_code_top": "awaiting_owner_followup"' in body
    assert b'"escalation_reason_top":' in body
    assert b'"pending_assignment_count": 1' in body
    assert b'"pending_escalation_count": 0' in body
    assert b'"resolved_count": 0' in body
    assert b'"needs_review_count": 0' in body
    assert b'"action_required_count": 1' in body
    assert b'"close_ready_count": 0' in body
    assert b'"by_workflow_lane": {' in body
    assert b'"by_queue_priority": {' in body
    assert b'"by_deadline_level": {' in body
    assert b'"by_batch_operation_hint": {' in body
    assert b'"by_escalation_tier": {}' in body
    assert b'"batch_suggestions": [' in body
    assert b'"action_bucket": "followup"' in body
    assert b'"batch_priority": "high"' in body
    assert b'"ordering_strategy": "queue_priority -> review_priority -> chapter_count -> confidence -> chapter_span_width -> first_chapter"' in body
    assert b'"suggested_cluster_order_details": [' in body
    assert b'"by_auto_next_action_code": {' in body
    assert b'"by_auto_next_action": {' in body


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
            review_actor="review-bot",
        )

    status, body = _call(
        f"/api/review-cluster-summary?run_id={run_id}&branch_id={branch_id}"
        f"&cluster_status=reviewed&review_owner=editor-a&review_result=confirmed-benign"
    )
    assert status == "200 OK"
    assert b'"cluster_count": 1' in body
    payload = json.loads(body)
    assert payload["filters"] == {
        "cluster_status": "reviewed",
        "review_owner": "editor-a",
        "review_result": "confirmed-benign",
    }
    assert payload["by_result"]["confirmed-benign"] == 1


def test_review_cluster_service_handles_missing_sqlite_review_tables(monkeypatch) -> None:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    with engine.begin() as conn:
        conn.execute(text('DROP TABLE cluster_review_event_records'))
        conn.execute(text('DROP TABLE cluster_review_records'))
    factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr("apps.api.app.main.create_session_factory", lambda settings=None: factory)

    with factory() as session:
        with pytest.raises(ClusterReviewStorageUnavailable):
            ClusterReviewService(session).read_branch("branch-x")
        with pytest.raises(ClusterReviewStorageUnavailable):
            ClusterReviewService(session).read_history("branch-x", "cluster-y")

    status, body = _call("/api/review-cluster-history?branch_id=branch-x&cluster_key=cluster-y")
    assert status == "200 OK"
    payload = json.loads(body)
    assert payload["review_storage_mode"] == "file-fallback"
    assert payload["items"] == []


def test_review_cluster_update_file_fallback_when_review_tables_missing(
    monkeypatch,
    tmp_path,
) -> None:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    with engine.begin() as conn:
        conn.execute(text('DROP TABLE cluster_review_event_records'))
        conn.execute(text('DROP TABLE cluster_review_records'))
    factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr("apps.api.app.main.create_session_factory", lambda settings=None: factory)
    settings = get_settings().model_copy(deep=True)
    settings.runtime_cache_dir = str(tmp_path / "runtime-cache")
    monkeypatch.setattr("apps.api.app.main.get_settings", lambda: settings)

    status, body = _call_post_json(
        "/api/review-cluster-update",
        {
            "branch_id": "branch-x",
            "cluster_key": "cluster-y",
            "cluster_status": "reviewed",
            "review_result": "confirmed-benign",
            "review_owner": "editor-fallback",
        },
    )
    payload = json.loads(body)
    assert status == "200 OK"
    assert payload["review_storage_mode"] == "file-fallback"
    fallback_state = read_cluster_review_state("branch-x", settings)
    assert fallback_state["cluster-y"]["review_owner"] == "editor-fallback"


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


def test_review_batch_execute_dry_run_and_apply(monkeypatch, tmp_path) -> None:
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
        bundle = ExportService(session).export_branch_bundle(run_id, branch_id)
        suggestion = bundle["review_summary"]["batch_suggestions"][0]
        cluster_key = suggestion["cluster_keys"][0]

    status, body = _call_post_json(
        "/api/review-batch-execute",
        {
            "run_id": run_id,
            "branch_id": branch_id,
            "action": "batch_review_assign",
            "hint_code": suggestion["hint_code"],
            "group_strategy": suggestion["group_strategy"],
            "group_key": suggestion["group_key"],
            "cluster_keys": [cluster_key],
            "review_owner": "editor-a",
            "review_actor": "review-bot",
            "review_notes": "dry-run preview",
            "dry_run": True,
        },
    )
    payload = json.loads(body)
    assert status == "200 OK"
    assert payload["dry_run"] is True
    assert payload["target_count"] == 1
    assert payload["skipped_count"] == 0
    assert payload["execution_id"]
    assert payload["preview"][0]["cluster_key"] == cluster_key

    status, body = _call_post_json(
        "/api/review-batch-execute",
        {
            "run_id": run_id,
            "branch_id": branch_id,
            "action": "batch_review_assign",
            "hint_code": suggestion["hint_code"],
            "group_strategy": suggestion["group_strategy"],
            "group_key": suggestion["group_key"],
            "cluster_keys": [cluster_key],
            "review_owner": "editor-a",
            "review_actor": "review-bot",
            "review_notes": "batch assign apply",
            "review_result": "deferred",
            "dry_run": False,
        },
    )
    payload = json.loads(body)
    assert status == "200 OK"
    assert payload["dry_run"] is False
    assert payload["success_count"] == 1
    assert payload["failed_count"] == 0
    assert payload["skipped_count"] == 0
    assert payload["execution_id"]
    assert payload["successes"][0]["cluster_key"] == cluster_key

    with factory() as session:
        state = ClusterReviewService(session).read_branch(branch_id)
        assert state[cluster_key]["review_owner"] == "editor-a"


def test_review_batch_execute_escalate(monkeypatch, tmp_path) -> None:
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
                "normalized_title": "升级测试",
                "chapter_summary": "问题簇需要升级处理。",
                "key_entities": ["卫图"],
                "key_events": ["升级处理"],
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
            cluster_status="escalated",
            review_result="needs-escalation",
            review_notes="需要升级",
            review_owner="editor-a",
            review_actor="review-bot",
        )
        bundle = ExportService(session).export_branch_bundle(run_id, branch_id)
        suggestion = bundle["review_summary"]["batch_suggestions"][0]
        cluster_key = suggestion["cluster_keys"][0]

    status, body = _call_post_json(
        "/api/review-batch-execute",
        {
            "run_id": run_id,
            "branch_id": branch_id,
            "action": "batch_escalate",
            "hint_code": suggestion["hint_code"],
            "group_strategy": suggestion["group_strategy"],
            "group_key": suggestion["group_key"],
            "cluster_keys": [cluster_key],
            "review_owner": "senior-editor",
            "review_actor": "review-bot",
            "review_notes": "批量升级执行",
            "dry_run": True,
        },
    )
    payload = json.loads(body)
    assert status == "200 OK"
    assert payload["dry_run"] is True
    assert payload["target_count"] == 1
    assert payload["skipped_count"] == 0
    assert payload["execution_id"]

    status, body = _call_post_json(
        "/api/review-batch-execute",
        {
            "run_id": run_id,
            "branch_id": branch_id,
            "action": "batch_escalate",
            "hint_code": suggestion["hint_code"],
            "group_strategy": suggestion["group_strategy"],
            "group_key": suggestion["group_key"],
            "cluster_keys": [cluster_key],
            "review_owner": "senior-editor",
            "review_actor": "review-bot",
            "review_notes": "批量升级执行",
            "dry_run": False,
        },
    )
    payload = json.loads(body)
    assert status == "200 OK"
    assert payload["success_count"] == 1
    assert payload["failed_count"] == 0
    assert payload["skipped_count"] == 0
    assert payload["execution_id"]

    with factory() as session:
        state = ClusterReviewService(session).read_branch(branch_id)
        assert state[cluster_key]["cluster_status"] == "escalated"
        assert state[cluster_key]["review_result"] == "needs-escalation"
        assert state[cluster_key]["review_owner"] == "senior-editor"


def test_review_batch_execute_close(monkeypatch, tmp_path) -> None:
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
                "normalized_title": "关闭测试",
                "chapter_summary": "问题簇可安全关闭。",
                "key_entities": ["卫图"],
                "key_events": ["关闭处理"],
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
            cluster_status="resolved",
            review_result="confirmed-benign",
            review_notes="满足关闭条件",
            review_owner="editor-a",
            review_actor="review-bot",
        )
        bundle = ExportService(session).export_branch_bundle(run_id, branch_id)
        suggestion = next(
            item
            for item in bundle["review_summary"]["batch_suggestions"]
            if item["hint_code"] == "batch_close_ready_candidates"
        )
        cluster_key = suggestion["cluster_keys"][0]

    status, body = _call_post_json(
        "/api/review-batch-execute",
        {
            "run_id": run_id,
            "branch_id": branch_id,
            "action": "batch_close",
            "hint_code": suggestion["hint_code"],
            "group_strategy": suggestion["group_strategy"],
            "group_key": suggestion["group_key"],
            "cluster_keys": [cluster_key],
            "review_owner": "editor-a",
            "review_actor": "review-bot",
            "review_notes": "批量关闭执行",
            "dry_run": True,
        },
    )
    payload = json.loads(body)
    assert status == "200 OK"
    assert payload["dry_run"] is True
    assert payload["preview"][0]["close_ready_gate"] is True
    assert payload["skipped_count"] == 0
    assert payload["execution_id"]

    status, body = _call_post_json(
        "/api/review-batch-execute",
        {
            "run_id": run_id,
            "branch_id": branch_id,
            "action": "batch_close",
            "hint_code": suggestion["hint_code"],
            "group_strategy": suggestion["group_strategy"],
            "group_key": suggestion["group_key"],
            "cluster_keys": [cluster_key],
            "review_owner": "editor-a",
            "review_actor": "review-bot",
            "review_notes": "批量关闭执行",
            "dry_run": False,
        },
    )
    payload = json.loads(body)
    assert status == "200 OK"
    assert payload["success_count"] == 1
    assert payload["failed_count"] == 0
    assert payload["skipped_count"] == 0
    assert payload["execution_id"]

    with factory() as session:
        state = ClusterReviewService(session).read_branch(branch_id)
        assert state[cluster_key]["cluster_status"] == "resolved"
        assert state[cluster_key]["review_result"] == "confirmed-benign"


def test_review_batch_execute_archive(monkeypatch, tmp_path) -> None:
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
                "normalized_title": "归档测试",
                "chapter_summary": "问题簇已关闭但未达到 close-ready。",
                "key_entities": ["卫图"],
                "key_events": ["归档处理"],
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
            cluster_status="resolved",
            review_result="deferred",
            review_notes="允许归档但不满足关闭门槛",
            review_owner="editor-a",
            review_actor="review-bot",
        )
        bundle = ExportService(session).export_branch_bundle(run_id, branch_id)
        suggestion = next(
            item
            for item in bundle["review_summary"]["batch_suggestions"]
            if item["hint_code"] == "batch_archive_candidates"
        )
        cluster_key = suggestion["cluster_keys"][0]

    status, body = _call_post_json(
        "/api/review-batch-execute",
        {
            "run_id": run_id,
            "branch_id": branch_id,
            "action": "batch_archive",
            "hint_code": suggestion["hint_code"],
            "group_strategy": suggestion["group_strategy"],
            "group_key": suggestion["group_key"],
            "cluster_keys": [cluster_key],
            "review_owner": "archiver",
            "review_actor": "review-bot",
            "review_notes": "批量归档执行",
            "dry_run": True,
        },
    )
    payload = json.loads(body)
    assert status == "200 OK"
    assert payload["dry_run"] is True
    assert payload["preview"][0]["close_ready_gate"] is False
    assert payload["skipped_count"] == 0
    assert payload["execution_id"]

    status, body = _call_post_json(
        "/api/review-batch-execute",
        {
            "run_id": run_id,
            "branch_id": branch_id,
            "action": "batch_archive",
            "hint_code": suggestion["hint_code"],
            "group_strategy": suggestion["group_strategy"],
            "group_key": suggestion["group_key"],
            "cluster_keys": [cluster_key],
            "review_owner": "archiver",
            "review_actor": "review-bot",
            "review_notes": "批量归档执行",
            "dry_run": False,
        },
    )
    payload = json.loads(body)
    assert status == "200 OK"
    assert payload["success_count"] == 1
    assert payload["failed_count"] == 0
    assert payload["skipped_count"] == 0
    assert payload["execution_id"]

    with factory() as session:
        state = ClusterReviewService(session).read_branch(branch_id)
        assert state[cluster_key]["cluster_status"] == "resolved"
        assert state[cluster_key]["review_result"] == "deferred"
        assert state[cluster_key]["review_owner"] == "archiver"


def test_review_batch_execute_reports_skipped_cluster_keys(monkeypatch, tmp_path) -> None:
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
        bundle = ExportService(session).export_branch_bundle(run_id, branch_id)
        suggestion = bundle["review_summary"]["batch_suggestions"][0]
        cluster_key = suggestion["cluster_keys"][0]

    status, body = _call_post_json(
        "/api/review-batch-execute",
        {
            "run_id": run_id,
            "branch_id": branch_id,
            "action": "batch_review_assign",
            "hint_code": suggestion["hint_code"],
            "group_strategy": suggestion["group_strategy"],
            "group_key": suggestion["group_key"],
            "cluster_keys": [cluster_key, "not-allowed"],
            "review_owner": "editor-a",
            "review_actor": "review-bot",
            "dry_run": True,
        },
    )
    payload = json.loads(body)
    assert status == "200 OK"
    assert payload["target_count"] == 1
    assert payload["skipped_count"] == 1
    assert payload["skipped"][0]["cluster_key"] == "not-allowed"


def test_review_batch_history_returns_audit_entries(monkeypatch, tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr("apps.api.app.main.create_session_factory", lambda settings=None: factory)
    settings = get_settings().model_copy(deep=True)
    settings.runtime_cache_dir = str(tmp_path / "runtime-cache")
    monkeypatch.setattr("apps.api.app.main.get_settings", lambda: settings)

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
        bundle = ExportService(session).export_branch_bundle(run_id, branch_id)
        suggestion = bundle["review_summary"]["batch_suggestions"][0]
        cluster_key = suggestion["cluster_keys"][0]

    _call_post_json(
        "/api/review-batch-execute",
        {
            "run_id": run_id,
            "branch_id": branch_id,
            "action": "batch_review_assign",
            "hint_code": suggestion["hint_code"],
            "group_strategy": suggestion["group_strategy"],
            "group_key": suggestion["group_key"],
            "cluster_keys": [cluster_key],
            "review_owner": "editor-a",
            "review_actor": "review-bot",
            "dry_run": True,
        },
    )
    status, body = _call(f"/api/review-batch-history?branch_id={branch_id}&limit=1")
    payload = json.loads(body)
    assert status == "200 OK"
    assert payload["branch_id"] == branch_id
    assert len(payload["items"]) == 1
    assert payload["items"][0]["action"] == "batch_review_assign"
    assert payload["items"][0]["dry_run"] is True
