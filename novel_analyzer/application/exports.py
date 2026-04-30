"""Export façades for future API/web callers."""

from __future__ import annotations

import json
from pathlib import Path

from novel_analyzer.application.dto import ExportRefs
from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.session import create_session_factory
from novel_analyzer.reporting.branch_report import render_branch_report
from novel_analyzer.services.export_service import ExportService


def export_branch_refs(
    *,
    run_id: str,
    branch_id: str,
    output_dir: str,
    database_url: str | None = None,
    settings: Settings | None = None,
) -> ExportRefs:
    """Export stable branch surfaces to filesystem-backed references."""

    runtime = (settings or get_settings()).model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)
    factory = create_session_factory(runtime)
    with factory() as session:
        export_service = ExportService(session)
        branch_bundle = export_service.export_branch_bundle(run_id, branch_id)
        branch_bundle_path = base / "branch_bundle.json"
        branch_bundle_path.write_text(
            json.dumps(branch_bundle, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        branch_qa_context = export_service.export_branch_qa_context(run_id, branch_id)
        branch_qa_context_path = base / "branch_qa_context.json"
        branch_qa_context_path.write_text(
            json.dumps(branch_qa_context, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        branch_report_path = base / "branch_report.md"
        branch_report_path.write_text(render_branch_report(branch_bundle), encoding="utf-8")
    return ExportRefs(
        branch_bundle_path=str(branch_bundle_path),
        branch_qa_context_path=str(branch_qa_context_path),
        branch_report_path=str(branch_report_path),
    )
