from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 2.0
_ENV_VAR = "N8N_WEBHOOK_PIPELINE_COMPLETE_URL"


def notify_pipeline_complete(
    *,
    branch_id: str,
    status: str,
    user_id: str = "local-default",
    metadata: dict[str, Any] | None = None,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> None:
    """Fire-and-forget POST to n8n pipeline-complete webhook.

    Reads the webhook URL from $N8N_WEBHOOK_PIPELINE_COMPLETE_URL.
    If unset/empty, returns immediately without contacting any service.
    All exceptions are caught and logged at WARNING — never propagates.

    Payload contains only run metadata (branch_id, status, user_id,
    optional metadata dict). User content (chapter text, prompts) is
    deliberately excluded from the wire format to keep the n8n side
    privacy-clean.
    """
    url = (os.getenv(_ENV_VAR) or "").strip()
    if not url:
        return

    payload = {
        "branch_id": branch_id,
        "status": status,
        "user_id": user_id,
        "metadata": metadata or {},
    }
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
    except httpx.TimeoutException:
        logger.warning("n8n notify timed out after %.1fs (branch=%s)", timeout_seconds, branch_id)
    except httpx.HTTPError as exc:
        logger.warning("n8n notify HTTP error (branch=%s): %s", branch_id, exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("n8n notify unexpected error (branch=%s): %s", branch_id, exc)
