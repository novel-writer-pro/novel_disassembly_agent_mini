"""Lightweight WSGI backend for the workbench prototype."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from dataclasses import asdict
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any, cast
from urllib.parse import parse_qs
from uuid import uuid4
from wsgiref.simple_server import WSGIServer, make_server
from wsgiref.types import StartResponse

from novel_analyzer.application import (
    get_branch_job_rows,
    cancel_pipeline_run,
    export_branch_refs,
    get_branch_snapshot,
    get_pipeline_run_status,
    get_run_snapshot,
    ingest_and_start_pipeline,
    list_pipeline_runs,
    pause_pipeline_run,
    recover_branch,
    resume_pipeline_run,
    start_pipeline_run_async,
    start_pipeline,
)
from novel_analyzer.application.queries import _derive_pipeline_state, _setup_status
from novel_analyzer.config.settings import get_settings
from novel_analyzer.database.models import (
    AnalysisRun,
    ChapterManifest,
    ChapterSegment,
    NovelSource,
    RunBranch,
)
from novel_analyzer.database.session import create_session_factory
from novel_analyzer.runtime.storage import (
    describe_runtime_storage,
    migrate_legacy_runtime_dirs,
    runtime_cache_root,
)
from novel_analyzer.runtime.provider_health import read_provider_health
from novel_analyzer.services.export_service import ExportService
from novel_analyzer.services.job_event_service import JobEventService
from novel_analyzer.services.qa_service import BranchQAService
from novel_analyzer.services.retrieval_service import RetrievalService
from novel_analyzer.services.status_service import StatusService


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    """Serve concurrent WSGI requests so long operations don't block the whole API."""

    daemon_threads = True


_RUNTIME_MIGRATED = False


def _json_payload(value: Any) -> bytes:
    if hasattr(value, "__dataclass_fields__") and not isinstance(value, type):
        value = asdict(value)
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


def _response(
    start_response: StartResponse,
    *,
    status: str,
    payload: Any,
) -> list[bytes]:
    body = _json_payload(payload)
    start_response(
        status,
        [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Headers", "Content-Type"),
            ("Access-Control-Allow-Methods", "GET,POST,OPTIONS"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


def _stream_response(
    start_response: StartResponse,
    event_iterable: Any,
) -> Any:
    start_response(
        "200 OK",
        [
            ("Content-Type", "text/event-stream; charset=utf-8"),
            ("Cache-Control", "no-cache"),
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Headers", "Content-Type"),
            ("Access-Control-Allow-Methods", "GET,POST,OPTIONS"),
            ("X-Accel-Buffering", "no"),
        ],
    )
    return event_iterable


def _sse_event(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


def _query(environ: dict[str, Any]) -> dict[str, str]:
    raw = parse_qs(environ.get("QUERY_STRING", ""))
    return {key: values[-1] for key, values in raw.items() if values}


def _json_body(environ: dict[str, Any]) -> dict[str, Any]:
    length = int(environ.get("CONTENT_LENGTH") or "0")
    if length <= 0:
        return {}
    raw = environ["wsgi.input"].read(length)
    if not raw:
        return {}
    return cast(dict[str, Any], json.loads(raw.decode("utf-8")))


def _multipart_form(environ: dict[str, Any]) -> dict[str, Any]:
    import cgi

    form = cgi.FieldStorage(fp=environ["wsgi.input"], environ=environ, keep_blank_values=True)
    payload: dict[str, Any] = {}
    for key in form.keys():
        item = form[key]
        if isinstance(item, list):
            item = item[-1]
        if getattr(item, "filename", None):
            payload[key] = item
        else:
            payload[key] = item.value
    return payload


def _body(environ: dict[str, Any]) -> dict[str, Any]:
    content_type = environ.get("CONTENT_TYPE", "")
    if content_type.startswith("application/json"):
        return _json_body(environ)
    if "multipart/form-data" in content_type:
        return _multipart_form(environ)
    if content_type.startswith("application/x-www-form-urlencoded"):
        length = int(environ.get("CONTENT_LENGTH") or "0")
        encoded = environ["wsgi.input"].read(length).decode("utf-8")
        return _query({"QUERY_STRING": encoded})
    return {}


def _require(params: dict[str, str], *keys: str) -> tuple[bool, str | None]:
    for key in keys:
        if not params.get(key):
            return False, key
    return True, None


def _mock_import(profile: str) -> dict[str, Any]:
    pipeline_state = "ready" if profile == "manual" else "auto_running"
    return {
        "novel_id": "novel-001",
        "manifest_id": "manifest-001",
        "run_id": "run-001",
        "branch_id": "branch-001",
        "pipeline_profile": profile,
        "pipeline_state": pipeline_state,
        "existing": False,
    }


def _mock_run_snapshot(profile: str) -> dict[str, Any]:
    return {
        "run_id": "run-001",
        "branch_id": "branch-001",
        "branch_name": "main",
        "pipeline_state": "ready" if profile == "manual" else "auto_running",
        "manifest_chapter_count": 120,
        "completed_chapters": 0 if profile == "manual" else 3,
        "failed_jobs": 0,
        "running_jobs": 0 if profile == "manual" else 1,
        "next_chapter": 1 if profile == "manual" else 4,
        "allowed_actions": ["start", "refresh"] if profile == "manual" else ["refresh"],
        "setup_status": "ok",
    }


def _mock_branch_snapshot(profile: str) -> dict[str, Any]:
    return {
        "branch_id": "branch-001",
        "pipeline_state": "ready" if profile == "manual" else "auto_running",
        "allowed_actions": ["start", "refresh", "export-basic"]
        if profile == "manual"
        else ["refresh"],
        "chapter_rows": [
            {
                "chapter_index": 1,
                "title": "第1章",
                "job_status": "validated",
                "has_artifact": True,
                "has_retrieval": True,
                "hook_score": 0.82,
                "needs_human_review": False,
                "summary": "样例章节摘要",
            }
        ],
        "failed_summary": [],
    }




def _runtime_cache_root() -> Path:
    return runtime_cache_root(get_settings())


def _migrate_legacy_runtime_dirs() -> None:
    global _RUNTIME_MIGRATED
    if _RUNTIME_MIGRATED:
        return

    migrate_legacy_runtime_dirs(get_settings())
    _RUNTIME_MIGRATED = True


def _stable_export_dir(run_id: str, branch_id: str) -> str:
    _migrate_legacy_runtime_dirs()
    base = _runtime_cache_root() / "runtime-exports" / run_id / branch_id / datetime.now().strftime('%Y%m%dT%H%M%S')
    base.mkdir(parents=True, exist_ok=True)
    return str(base)

def _persist_uploaded_text(file_item: Any) -> str:
    _migrate_legacy_runtime_dirs()
    filename = Path(getattr(file_item, "filename", "upload.txt")).name or "upload.txt"
    target_dir = _runtime_cache_root() / "uploads"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{uuid4().hex}-{filename}"

    with target_path.open("wb") as handle:
        shutil.copyfileobj(file_item.file, handle)

    return str(target_path.resolve())


def _resolve_source_path(path_value: str) -> Path:
    _migrate_legacy_runtime_dirs()
    path = Path(path_value)
    if path.exists():
        return path

    legacy_marker = ".omx/uploads"
    if legacy_marker in path_value:
        migrated = _runtime_cache_root() / "uploads" / path.name
        if migrated.exists():
            return migrated
        legacy_path = get_settings().legacy_runtime_dir / "uploads" / path.name
        if legacy_path.exists():
            return legacy_path

    raise FileNotFoundError(f"No such file or directory: '{path_value}'")


def _export_query_runtime(params: dict[str, str]) -> Any:
    runtime = get_settings().model_copy(deep=True)
    if params.get("database_url"):
        runtime.database_url = params["database_url"]
    return runtime


def _chapter_source_payload(
    *,
    branch_id: str,
    chapter_index: int,
    database_url: str | None,
) -> dict[str, Any]:
    runtime = get_settings().model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    factory = create_session_factory(runtime)
    with factory() as session:
        branch = session.get(RunBranch, branch_id)
        if branch is None:
            raise ValueError("branch not found")
        manifest = session.get(ChapterManifest, branch.run.manifest_id)
        if manifest is None:
            raise ValueError("manifest not found")
        segment = session.scalar(
            session.query(ChapterSegment)
            .filter(ChapterSegment.manifest_id == manifest.id)
            .filter(ChapterSegment.chapter_index == chapter_index)
            .statement
        )
        if segment is None:
            raise ValueError("chapter segment not found")
        novel = session.get(NovelSource, manifest.novel_id)
        if novel is None:
            raise ValueError("novel source not found")
        text = _resolve_source_path(novel.source_path).read_text(encoding="utf-8")
        content = text[segment.start_offset:segment.end_offset].strip()
        return {
            "chapter_index": chapter_index,
            "raw_heading": segment.raw_heading,
            "normalized_title": segment.normalized_title,
            "start_offset": segment.start_offset,
            "end_offset": segment.end_offset,
            "source_excerpt": content,
        }


def _library_payload(database_url: str | None, limit: int) -> dict[str, Any]:
    runtime = get_settings().model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    factory = create_session_factory(runtime)
    rows: list[dict[str, Any]] = []
    with factory() as session:
        branches = session.scalars(
            session.query(RunBranch)
            .order_by(RunBranch.updated_at.desc())
            .limit(limit)
            .statement
        ).all()
        for branch in branches:
            run = session.get(AnalysisRun, branch.run_id)
            if run is None:
                continue
            novel = session.get(NovelSource, run.novel_id)
            manifest = session.get(ChapterManifest, run.manifest_id)
            if novel is None or manifest is None:
                continue
            status = StatusService(session).get_run_status(run.id, branch.id)
            rows.append(
                {
                    "novel_id": novel.id,
                    "title": novel.title,
                    "run_id": run.id,
                    "branch_id": branch.id,
                    "branch_name": branch.name,
                    "pipeline_state": _derive_pipeline_state(session, run.id, branch.id, status.next_chapter),
                    "completed_chapters": status.completed_chapters,
                    "manifest_chapter_count": status.manifest_chapter_count,
                    "next_chapter": status.next_chapter,
                    "failed_jobs": status.failed_jobs,
                    "running_jobs": status.running_jobs,
                    "setup_status": _setup_status(session, run.id),
                    "updated_at": branch.updated_at.isoformat() if branch.updated_at else None,
                }
            )
    return {"items": rows}


def _job_events_payload(branch_id: str, database_url: str | None, limit: int) -> dict[str, Any]:
    runtime = get_settings().model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    factory = create_session_factory(runtime)
    with factory() as session:
        rows = JobEventService(session).list_for_branch(branch_id, limit)
    return {
        "items": [
            {
                "id": row.id,
                "run_id": row.run_id,
                "branch_id": row.branch_id,
                "chapter_index": row.chapter_index,
                "event_type": row.event_type,
                "stage": row.stage,
                "level": row.level,
                "message": row.message,
                "payload_json": row.payload_json,
                "created_at": row.created_at.isoformat() if hasattr(row.created_at, "isoformat") else str(row.created_at),
            }
            for row in rows
        ]
    }


def application(environ: dict[str, Any], start_response: StartResponse) -> list[bytes]:
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")
    params = _query(environ)

    if method == "OPTIONS":
        return _response(start_response, status="200 OK", payload={"ok": True})

    if method not in {"GET", "POST"}:
        return _response(
            start_response,
            status="405 Method Not Allowed",
            payload={"error": "only GET/POST are supported in the current prototype"},
        )

    if path == "/health":
        return _response(
            start_response,
            status="200 OK",
            payload={"status": "ok", "service": "apps/api"},
        )

    if path == "/api/meta":
        return _response(
            start_response,
            status="200 OK",
            payload={
                "service": "novel-analyzer-api-prototype",
                "available_endpoints": [
                    "/health",
                    "/api/meta",
                    "/api/mock/import",
                    "/api/run-snapshot",
                    "/api/branch-snapshot",
                    "/api/chapter-bundle",
                    "/api/chapter-qa-context",
                    "/api/chapter-source",
                    "/api/chapter-jobs",
                    "/api/library",
                    "/api/job-events",
                    "/api/pipeline/start-range",
                    "/api/pipeline/status",
                    "/api/pipeline/runs",
                    "/api/pipeline/pause",
                    "/api/pipeline/resume",
                    "/api/pipeline/cancel",
                    "/api/runtime-health",
                    "/api/provider-health",
                    "/api/search-branch",
                    "/api/ask-branch",
                    "/api/ask-branch-stream",
                    "/api/branch-exports",
                    "/api/download",
                ],
                "notes": [
                    "Current backend is dependency-light WSGI JSON.",
                    "Real write-side import/upload endpoints are still future work.",
                ],
            },
        )

    if path == "/api/mock/import":
        profile = params.get("profile", "auto-lite")
        return _response(
            start_response,
            status="200 OK",
            payload={
                "import_result": _mock_import(profile),
                "run_snapshot": _mock_run_snapshot(profile),
                "branch_snapshot": _mock_branch_snapshot(profile),
            },
        )

    if path == "/api/import" and method == "POST":
        body = _body(environ)
        file_item = body.get("file")
        if file_item is None:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": "missing uploaded file"},
            )
        path_on_disk = _persist_uploaded_text(file_item)
        title = str(body.get("title") or "")
        profile = str(body.get("pipeline_profile") or "auto-lite")
        database_url = str(body.get("database_url") or "") or None
        max_chapters_raw = str(body.get("max_chapters") or "").strip()
        max_chapters = int(max_chapters_raw) if max_chapters_raw else None
        try:
            result = ingest_and_start_pipeline(
                path=path_on_disk,
                title=title or None,
                pipeline_profile=profile,
                max_chapters=max_chapters,
                database_url=database_url,
            )
            run_snapshot = None
            branch_snapshot = None
            if result.run_id and result.branch_id:
                run_snapshot = get_run_snapshot(
                    run_id=result.run_id,
                    branch_id=result.branch_id,
                    database_url=database_url,
                )
                branch_snapshot = get_branch_snapshot(
                    run_id=result.run_id,
                    branch_id=result.branch_id,
                    database_url=database_url,
                )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(
            start_response,
            status="200 OK",
            payload={
                "import_result": asdict(result),
                "run_snapshot": asdict(run_snapshot) if run_snapshot else None,
                "branch_snapshot": asdict(branch_snapshot) if branch_snapshot else None,
            },
        )

    if path == "/api/start" and method == "POST":
        body = _body(environ)
        run_id = str(body.get("run_id") or "")
        branch_id = str(body.get("branch_id") or "")
        if not run_id or not branch_id:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": "run_id and branch_id are required"},
            )
        profile = str(body.get("pipeline_profile") or "auto-lite")
        database_url = str(body.get("database_url") or "") or None
        max_chapters_raw = str(body.get("max_chapters") or "").strip()
        max_chapters = int(max_chapters_raw) if max_chapters_raw else None
        try:
            processed_chapters, next_chapter, pipeline_state = start_pipeline(
                run_id=run_id,
                branch_id=branch_id,
                pipeline_profile=profile,
                max_chapters=max_chapters,
                database_url=database_url,
            )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(
            start_response,
            status="200 OK",
            payload={
                "processed_chapters": processed_chapters,
                "next_chapter": next_chapter,
                "pipeline_state": pipeline_state,
            },
        )

    if path == "/api/recovery" and method == "POST":
        body = _body(environ)
        run_id = str(body.get("run_id") or "")
        branch_id = str(body.get("branch_id") or "")
        action = str(body.get("action") or "")
        if not run_id or not branch_id or not action:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": "run_id, branch_id and action are required"},
            )
        chapter_index_raw = str(body.get("chapter_index") or "").strip()
        chapter_index = int(chapter_index_raw) if chapter_index_raw else None
        database_url = str(body.get("database_url") or "") or None
        try:
            recovery_result = recover_branch(
                action=action,
                run_id=run_id,
                branch_id=branch_id,
                chapter_index=chapter_index,
                database_url=database_url,
            )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=recovery_result)

    if path == "/api/run-snapshot":
        ok, missing = _require(params, "run_id", "branch_id")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        try:
            run_snapshot = get_run_snapshot(
                run_id=params["run_id"],
                branch_id=params["branch_id"],
                database_url=params.get("database_url"),
            )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=run_snapshot)

    if path == "/api/branch-snapshot":
        ok, missing = _require(params, "run_id", "branch_id")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        try:
            branch_snapshot = get_branch_snapshot(
                run_id=params["run_id"],
                branch_id=params["branch_id"],
                database_url=params.get("database_url"),
            )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=branch_snapshot)

    if path == "/api/chapter-bundle":
        ok, missing = _require(params, "branch_id", "chapter_index")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        runtime = get_settings().model_copy(deep=True)
        if params.get("database_url"):
            runtime.database_url = params["database_url"]
        try:
            factory = create_session_factory(runtime)
            with factory() as session:
                bundle = ExportService(session).export_chapter_bundle(
                    params["branch_id"],
                    int(params["chapter_index"]),
                )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=bundle)

    if path == "/api/chapter-qa-context":
        ok, missing = _require(params, "branch_id", "chapter_index")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        runtime = get_settings().model_copy(deep=True)
        if params.get("database_url"):
            runtime.database_url = params["database_url"]
        try:
            factory = create_session_factory(runtime)
            with factory() as session:
                qa_payload = ExportService(session).export_chapter_qa_context(
                    params["branch_id"],
                    int(params["chapter_index"]),
                )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=qa_payload)

    if path == "/api/chapter-source":
        ok, missing = _require(params, "branch_id", "chapter_index")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        try:
            payload = _chapter_source_payload(
                branch_id=params["branch_id"],
                chapter_index=int(params["chapter_index"]),
                database_url=params.get("database_url"),
            )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=payload)

    if path == "/api/chapter-jobs":
        ok, missing = _require(params, "branch_id")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        try:
            rows = get_branch_job_rows(
                branch_id=params["branch_id"],
                database_url=params.get("database_url"),
                limit=int(params.get("limit", "200")),
            )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload={"items": [asdict(item) for item in rows]})

    if path == "/api/library":
        database_url = params.get("database_url")
        limit = int(params.get("limit", "100"))
        try:
            payload = _library_payload(database_url, limit)
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=payload)

    if path == "/api/job-events":
        ok, missing = _require(params, "branch_id")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        database_url = params.get("database_url")
        limit = int(params.get("limit", "100"))
        try:
            payload = _job_events_payload(params["branch_id"], database_url, limit)
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=payload)

    if path == "/api/pipeline/start-range" and method == "POST":
        body = _body(environ)
        run_id = str(body.get("run_id") or "")
        branch_id = str(body.get("branch_id") or "")
        if not run_id or not branch_id:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": "run_id and branch_id are required"},
            )
        try:
            snapshot = start_pipeline_run_async(
                run_id=run_id,
                branch_id=branch_id,
                target_from_chapter=int(str(body.get("from_chapter"))) if body.get("from_chapter") else None,
                target_to_chapter=int(str(body.get("to_chapter"))) if body.get("to_chapter") else None,
                concurrency=int(str(body.get("concurrency") or "1")),
                provider_profile=str(body.get("provider_profile") or "") or None,
                created_by="api",
                database_url=str(body.get("database_url") or "") or None,
            )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=asdict(snapshot))

    if path == "/api/pipeline/status":
        ok, missing = _require(params, "pipeline_run_id")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        try:
            snapshot = get_pipeline_run_status(
                pipeline_run_id=params["pipeline_run_id"],
                database_url=params.get("database_url"),
            )
        except Exception as exc:  # noqa: BLE001
            return _response(start_response, status="500 Internal Server Error", payload={"error": str(exc)})
        return _response(start_response, status="200 OK", payload=asdict(snapshot))

    if path == "/api/pipeline/runs":
        ok, missing = _require(params, "branch_id")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        try:
            rows = list_pipeline_runs(
                branch_id=params["branch_id"],
                limit=int(params.get("limit", "20")),
                database_url=params.get("database_url"),
            )
        except Exception as exc:  # noqa: BLE001
            return _response(start_response, status="500 Internal Server Error", payload={"error": str(exc)})
        return _response(start_response, status="200 OK", payload={"items": [asdict(item) for item in rows]})

    if path in {"/api/pipeline/pause", "/api/pipeline/resume", "/api/pipeline/cancel"} and method == "POST":
        body = _body(environ)
        pipeline_run_id = str(body.get("pipeline_run_id") or "")
        if not pipeline_run_id:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": "pipeline_run_id is required"},
            )
        try:
            if path.endswith("/pause"):
                snapshot = pause_pipeline_run(pipeline_run_id=pipeline_run_id, database_url=str(body.get("database_url") or "") or None)
            elif path.endswith("/resume"):
                snapshot = resume_pipeline_run(pipeline_run_id=pipeline_run_id, database_url=str(body.get("database_url") or "") or None)
            else:
                snapshot = cancel_pipeline_run(pipeline_run_id=pipeline_run_id, database_url=str(body.get("database_url") or "") or None)
        except Exception as exc:  # noqa: BLE001
            return _response(start_response, status="500 Internal Server Error", payload={"error": str(exc)})
        return _response(start_response, status="200 OK", payload=asdict(snapshot))

    if path == "/api/runtime-health":
        try:
            report = describe_runtime_storage(get_settings())
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=asdict(report))

    if path == "/api/provider-health":
        try:
            report = read_provider_health(get_settings())
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=asdict(report))

    if path == "/api/search-branch":
        ok, missing = _require(params, "branch_id", "q")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        runtime = get_settings().model_copy(deep=True)
        if params.get("database_url"):
            runtime.database_url = params["database_url"]
        limit = int(params.get("limit", "8"))
        try:
            factory = create_session_factory(runtime)
            with factory() as session:
                hits = RetrievalService(session, runtime).search_branch(params["branch_id"], params["q"], limit)
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload={"hits": [asdict(hit) for hit in hits]})

    if path == "/api/ask-branch" and method == "POST":
        body = _body(environ)
        branch_id = str(body.get("branch_id") or "")
        question = str(body.get("question") or "")
        if not branch_id or not question:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": "branch_id and question are required"},
            )
        runtime = get_settings().model_copy(deep=True)
        database_url = str(body.get("database_url") or "") or None
        if database_url:
            runtime.database_url = database_url
        limit = int(str(body.get("limit") or "6"))
        try:
            factory = create_session_factory(runtime)
            with factory() as session:
                result = BranchQAService(session, runtime).answer_question(branch_id, question, limit)
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=result.model_dump(mode="json"))

    if path == "/api/ask-branch-stream" and method == "POST":
        body = _body(environ)
        branch_id = str(body.get("branch_id") or "")
        question = str(body.get("question") or "")
        if not branch_id or not question:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": "branch_id and question are required"},
            )
        runtime = get_settings().model_copy(deep=True)
        database_url = str(body.get("database_url") or "") or None
        if database_url:
            runtime.database_url = database_url
        limit = int(str(body.get("limit") or "6"))

        def _event_iter() -> Any:
            yield _sse_event({"type": "status", "message": "正在检索相关章节…"})
            try:
                factory = create_session_factory(runtime)
                with factory() as session:
                    hits = RetrievalService(session, runtime).search_branch(branch_id, question, limit)
                    yield _sse_event(
                        {
                            "type": "retrieval",
                            "hits": [asdict(hit) for hit in hits],
                        }
                    )
                    yield _sse_event({"type": "status", "message": "正在结合证据与图谱线索组织回答…"})
                    result = BranchQAService(session, runtime).answer_question(branch_id, question, limit)
                answer_text = result.answer or ""
                for index in range(0, len(answer_text), 20):
                    yield _sse_event({"type": "delta", "delta": answer_text[index:index + 20]})
                yield _sse_event({"type": "final", "result": result.model_dump(mode="json")})
            except Exception as exc:  # noqa: BLE001
                yield _sse_event({"type": "error", "error": str(exc)})

        return _stream_response(start_response, _event_iter())

    if path == "/api/branch-exports":
        ok, missing = _require(params, "run_id", "branch_id")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        try:
            refs = export_branch_refs(
                run_id=params["run_id"],
                branch_id=params["branch_id"],
                output_dir=_stable_export_dir(params["run_id"], params["branch_id"]),
                database_url=params.get("database_url"),
            )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(
            start_response,
            status="200 OK",
            payload={
                "branch_bundle": {
                    "download_ref": f"/api/download?path={refs.branch_bundle_path}",
                    "content_type": "application/json",
                },
                "branch_qa_context": {
                    "download_ref": f"/api/download?path={refs.branch_qa_context_path}",
                    "content_type": "application/json",
                },
                "branch_report": {
                    "download_ref": f"/api/download?path={refs.branch_report_path}",
                    "content_type": "text/markdown",
                },
            },
        )

    if path == "/api/download":
        ok, missing = _require(params, "path")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        file_path = Path(params["path"])
        if not file_path.exists() or not file_path.is_file():
            return _response(
                start_response,
                status="404 Not Found",
                payload={"error": "export file not found"},
            )
        content_type = (
            "text/markdown; charset=utf-8"
            if file_path.suffix == ".md"
            else "application/json; charset=utf-8"
        )
        file_body = file_path.read_bytes()
        start_response(
            "200 OK",
            [
                ("Content-Type", content_type),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(file_body))),
                ("Content-Disposition", f'attachment; filename="{file_path.name}"'),
            ],
        )
        return [file_body]

    return _response(
        start_response,
        status="404 Not Found",
        payload={"error": "route not found"},
    )


def main() -> None:
    """Run the prototype backend locally."""

    host = "127.0.0.1"
    port = 8011
    _migrate_legacy_runtime_dirs()
    with make_server(host, port, application, server_class=ThreadingWSGIServer) as httpd:
        print(f"apps/api running on http://{host}:{port}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
