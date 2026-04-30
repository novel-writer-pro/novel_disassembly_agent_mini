"""CLI script for PostgreSQL capability checks."""

from __future__ import annotations

from novel_analyzer.config.settings import get_settings
from novel_analyzer.database.postgres_checks import postgres_capability_report


def main() -> int:
    try:
        report = postgres_capability_report(get_settings())
    except ValueError as exc:
        print(str(exc))
        return 1
    print(f"database_exists={str(report.database_exists).lower()}")
    print(f"can_connect={str(report.can_connect).lower()}")
    print(f"initialized_schema={str(report.initialized_schema).lower()}")
    print(f"server_version={report.server_version}")
    print(f"installed_extensions={','.join(report.installed_extensions)}")
    print(f"available_text_search_configs={','.join(report.available_text_search_configs)}")
    print(f"missing_tables={','.join(report.missing_tables)}")
    print(f"missing_extensions={','.join(report.missing_extensions)}")
    print(f"ok={str(report.ok).lower()}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
