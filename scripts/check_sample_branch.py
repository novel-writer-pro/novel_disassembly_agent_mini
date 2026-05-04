"""CLI smoke check for a sample branch export path."""

from __future__ import annotations

import argparse
from pathlib import Path

from novel_analyzer.config.settings import get_settings, Settings
from novel_analyzer.database.postgres_checks import postgres_capability_report
from novel_analyzer.database.session import create_session_factory
from novel_analyzer.reporting.branch_report import render_branch_report
from novel_analyzer.services.export_service import ExportService


def _settings(database_url: str | None = None) -> Settings:
    runtime = get_settings().model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    return runtime


def export_branch_report_markdown(
    *,
    run_id: str,
    branch_id: str,
    output_path: Path,
    settings: Settings,
) -> None:
    factory = create_session_factory(settings)
    with factory() as session:
        bundle = ExportService(session).export_branch_bundle(run_id, branch_id)
    output_path.write_text(render_branch_report(bundle), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run PostgreSQL + branch report smoke checks")
    parser.add_argument("run_id")
    parser.add_argument("branch_id")
    parser.add_argument("output_path")
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args(argv)

    try:
        settings = _settings(args.database_url)
        report = postgres_capability_report(settings)
    except ValueError as exc:
        print(str(exc))
        return 1

    print(f"database_exists={str(report.database_exists).lower()}")
    print(f"can_connect={str(report.can_connect).lower()}")
    print(f"initialized_schema={str(report.initialized_schema).lower()}")
    print(f"server_version={report.server_version}")
    print(f"missing_tables={','.join(report.missing_tables)}")
    print(f"missing_extensions={','.join(report.missing_extensions)}")
    if report.missing_cluster_review_columns:
        items = [
            f"{table}:{','.join(columns)}"
            for table, columns in sorted(report.missing_cluster_review_columns.items())
        ]
        print(f"missing_cluster_review_columns={';'.join(items)}")
    else:
        print("missing_cluster_review_columns=")
    print(f"ok={str(report.ok).lower()}")
    if not report.ok:
        return 1

    output_path = Path(args.output_path)
    export_branch_report_markdown(
        run_id=args.run_id,
        branch_id=args.branch_id,
        output_path=output_path,
        settings=settings,
    )
    print(f"report_path={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
