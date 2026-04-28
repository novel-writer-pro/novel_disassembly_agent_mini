"""Managed runtime storage helpers for uploads/exports compatibility."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from novel_analyzer.config.settings import Settings, get_settings


@dataclass(frozen=True, slots=True)
class RuntimeStorageReport:
    cache_root: str
    legacy_root: str
    cache_upload_files: int
    cache_export_files: int
    legacy_upload_files: int
    legacy_export_files: int
    missing_from_cache: int
    migrated_this_run: int


def runtime_cache_root(settings: Settings | None = None) -> Path:
    runtime = settings or get_settings()
    root = runtime.resolved_runtime_cache_dir
    root.mkdir(parents=True, exist_ok=True)
    return root


def _count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file())


def migrate_legacy_runtime_dirs(settings: Settings | None = None) -> RuntimeStorageReport:
    runtime = settings or get_settings()
    legacy_root = runtime.legacy_runtime_dir
    cache_root = runtime_cache_root(runtime)

    migration_pairs = [
        (legacy_root / "uploads", cache_root / "uploads"),
        (legacy_root / "runtime-exports", cache_root / "runtime-exports"),
    ]

    migrated_this_run = 0
    missing_from_cache = 0
    for legacy_dir, target_dir in migration_pairs:
        if not legacy_dir.exists():
            continue
        target_dir.mkdir(parents=True, exist_ok=True)
        for source in legacy_dir.rglob("*"):
            if not source.is_file():
                continue
            relative = source.relative_to(legacy_dir)
            destination = target_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                continue
            shutil.copy2(source, destination)
            migrated_this_run += 1
            missing_from_cache += 1

    return describe_runtime_storage(runtime, migrated_this_run=migrated_this_run)


def describe_runtime_storage(
    settings: Settings | None = None,
    *,
    migrated_this_run: int = 0,
) -> RuntimeStorageReport:
    runtime = settings or get_settings()
    legacy_root = runtime.legacy_runtime_dir
    cache_root = runtime_cache_root(runtime)

    cache_uploads = cache_root / "uploads"
    cache_exports = cache_root / "runtime-exports"
    legacy_uploads = legacy_root / "uploads"
    legacy_exports = legacy_root / "runtime-exports"

    cache_upload_files = _count_files(cache_uploads)
    cache_export_files = _count_files(cache_exports)
    legacy_upload_files = _count_files(legacy_uploads)
    legacy_export_files = _count_files(legacy_exports)

    missing_from_cache = max(legacy_upload_files - cache_upload_files, 0) + max(
        legacy_export_files - cache_export_files,
        0,
    )

    return RuntimeStorageReport(
        cache_root=str(cache_root),
        legacy_root=str(legacy_root),
        cache_upload_files=cache_upload_files,
        cache_export_files=cache_export_files,
        legacy_upload_files=legacy_upload_files,
        legacy_export_files=legacy_export_files,
        missing_from_cache=missing_from_cache,
        migrated_this_run=migrated_this_run,
    )
