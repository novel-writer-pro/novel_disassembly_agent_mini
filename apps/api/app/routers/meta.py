from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.routing import APIRoute

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "apps/api"}


def _collect_endpoint_specs(request: Request) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    specs: list[dict[str, str]] = []
    for route in request.app.routes:
        if not isinstance(route, APIRoute):
            continue
        path = route.path
        if path in {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}:
            continue
        for method in route.methods or set():
            if method in {"HEAD", "OPTIONS"}:
                continue
            key = (method, path)
            if key in seen:
                continue
            seen.add(key)
            specs.append({"method": method, "path": path})
    specs.sort(key=lambda s: (s["path"], s["method"]))
    return specs


@router.get("/api/meta")
def api_meta(request: Request) -> dict:
    specs = _collect_endpoint_specs(request)
    return {
        "service": "novel-analyzer-api-prototype",
        "available_endpoints": [item["path"] for item in specs],
        "available_endpoint_specs": specs,
        "notes": [
            "Current backend is dependency-light WSGI JSON.",
            "The import/upload endpoint is available; broader write-side workflow surfaces remain incrementally productized.",
        ],
    }


@router.get("/api/mock/import")
def mock_import(profile: str = Query("auto-lite")) -> dict:
    from apps.api.app.main import (
        _mock_import,
        _mock_run_snapshot,
        _mock_branch_snapshot,
    )
    return {
        "import_result": _mock_import(profile),
        "run_snapshot": _mock_run_snapshot(profile),
        "branch_snapshot": _mock_branch_snapshot(profile),
    }



@router.get("/api/download")
def download(path: str = Query(...)):
    from pathlib import Path as _Path
    from fastapi.responses import JSONResponse, FileResponse
    file_path = _Path(path)
    if not file_path.exists() or not file_path.is_file():
        return JSONResponse(status_code=404, content={"error": "export file not found"})
    media_type = "text/markdown; charset=utf-8" if file_path.suffix == ".md" else "application/json; charset=utf-8"
    return FileResponse(str(file_path), media_type=media_type, filename=file_path.name)


@router.get("/api/runtime-health")
def runtime_health():
    from dataclasses import asdict
    from fastapi.responses import JSONResponse
    from novel_analyzer.config.settings import get_settings
    from novel_analyzer.runtime.storage import describe_runtime_storage
    try:
        report = describe_runtime_storage(get_settings())
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})
    return asdict(report)


@router.get("/api/provider-health")
def provider_health():
    from dataclasses import asdict
    from fastapi.responses import JSONResponse
    from novel_analyzer.config.settings import get_settings
    from novel_analyzer.runtime.provider_health import read_provider_health
    try:
        report = read_provider_health(get_settings())
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})
    return asdict(report)


@router.get("/api/quality-dashboard")
def quality_dashboard(
    branch_id: str = Query(..., description="branch id"),
    database_url: str | None = Query(None),
):
    from fastapi.responses import JSONResponse
    from apps.api.app.main import _quality_dashboard_payload
    try:
        return _quality_dashboard_payload(branch_id, database_url)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})
