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
