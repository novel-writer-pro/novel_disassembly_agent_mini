"""Runtime storage for batch review execution audit entries."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.runtime.storage import runtime_cache_root


def _batch_execution_root(settings: Settings | None = None) -> Path:
    root = runtime_cache_root(settings) / "review-batch-execution"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _batch_execution_path(branch_id: str, settings: Settings | None = None) -> Path:
    return _batch_execution_root(settings) / f"{branch_id}.json"


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def read_batch_execution_history(
    branch_id: str,
    settings: Settings | None = None,
) -> list[dict[str, object]]:
    runtime = settings or get_settings()
    path = _batch_execution_path(branch_id, runtime)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def write_batch_execution_entry(
    *,
    branch_id: str,
    action: str,
    hint_code: str,
    group_strategy: str,
    group_key: str,
    dry_run: bool,
    target_count: int,
    success_count: int,
    failed_count: int,
    skipped_count: int,
    preview: list[dict[str, object]],
    successes: list[dict[str, object]],
    failed: list[dict[str, object]],
    skipped: list[dict[str, object]],
    settings: Settings | None = None,
) -> dict[str, object]:
    runtime = settings or get_settings()
    history = read_batch_execution_history(branch_id, runtime)
    entry = {
        "execution_id": str(uuid4()),
        "created_at": _utc_timestamp(),
        "branch_id": branch_id,
        "action": action,
        "hint_code": hint_code,
        "group_strategy": group_strategy,
        "group_key": group_key,
        "dry_run": dry_run,
        "target_count": target_count,
        "success_count": success_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "preview": preview,
        "successes": successes,
        "failed": failed,
        "skipped": skipped,
    }
    history.append(entry)
    _batch_execution_path(branch_id, runtime).write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return entry
