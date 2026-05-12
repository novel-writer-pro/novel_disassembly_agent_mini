"""Lightweight provider health persistence for UI/runtime diagnostics."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.runtime.storage import runtime_cache_root

DECAY_WINDOW_SECONDS = 300
SUCCESS_DECAY_RATE = 2


@dataclass(frozen=True, slots=True)
class ProviderHealthReport:
    provider_name: str
    model_name: str
    last_status: str
    degraded_events: int
    success_events: int
    last_error: str | None
    last_updated_at: str | None


def _provider_health_path(settings: Settings | None = None) -> Path:
    runtime = settings or get_settings()
    return runtime_cache_root(runtime) / "provider-health.json"


def read_provider_health(settings: Settings | None = None) -> ProviderHealthReport:
    runtime = settings or get_settings()
    path = _provider_health_path(runtime)
    if not path.exists():
        return ProviderHealthReport(
            provider_name=runtime.llm_provider_name,
            model_name=runtime.llm_qa_model_name,
            last_status="unknown",
            degraded_events=0,
            success_events=0,
            last_error=None,
            last_updated_at=None,
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ProviderHealthReport(
            provider_name=runtime.llm_provider_name,
            model_name=runtime.llm_qa_model_name,
            last_status="unknown",
            degraded_events=0,
            success_events=0,
            last_error="provider health file is unreadable",
            last_updated_at=None,
        )
    return ProviderHealthReport(
        provider_name=str(payload.get("provider_name") or runtime.llm_provider_name),
        model_name=str(payload.get("model_name") or runtime.llm_qa_model_name),
        last_status=str(payload.get("last_status") or "unknown"),
        degraded_events=int(payload.get("degraded_events") or 0),
        success_events=int(payload.get("success_events") or 0),
        last_error=str(payload["last_error"]) if payload.get("last_error") else None,
        last_updated_at=str(payload["last_updated_at"]) if payload.get("last_updated_at") else None,
    )


def _apply_time_decay(current: ProviderHealthReport) -> int:
    """Decay degraded_events if enough time has passed since last update."""
    if not current.last_updated_at or current.degraded_events == 0:
        return current.degraded_events
    try:
        last_update = datetime.fromisoformat(current.last_updated_at)
        elapsed = (datetime.now(timezone.utc) - last_update).total_seconds()
        decay_periods = int(elapsed / DECAY_WINDOW_SECONDS)
        if decay_periods > 0:
            return max(0, current.degraded_events - decay_periods * SUCCESS_DECAY_RATE)
    except (ValueError, TypeError):
        pass
    return current.degraded_events


def record_provider_health(
    *,
    ok: bool,
    error_message: str | None = None,
    settings: Settings | None = None,
) -> ProviderHealthReport:
    runtime = settings or get_settings()
    current = read_provider_health(runtime)
    decayed_degraded = _apply_time_decay(current)

    if ok:
        new_degraded = max(0, decayed_degraded - SUCCESS_DECAY_RATE)
        new_success = current.success_events + 1
    else:
        new_degraded = decayed_degraded + 1
        new_success = current.success_events

    next_report = ProviderHealthReport(
        provider_name=runtime.llm_provider_name,
        model_name=runtime.llm_qa_model_name,
        last_status="ok" if ok else "degraded",
        degraded_events=new_degraded,
        success_events=new_success,
        last_error=None if ok else (error_message or current.last_error),
        last_updated_at=datetime.now(timezone.utc).isoformat(),
    )
    path = _provider_health_path(runtime)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(next_report), ensure_ascii=False, indent=2), encoding="utf-8")
    return next_report
