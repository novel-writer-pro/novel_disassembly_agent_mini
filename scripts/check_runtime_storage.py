"""Inspect managed runtime storage and optionally migrate legacy .omx data."""

from __future__ import annotations

import argparse

from novel_analyzer.config.settings import get_settings
from novel_analyzer.runtime.storage import describe_runtime_storage, migrate_legacy_runtime_dirs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrate", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    report = migrate_legacy_runtime_dirs(settings) if args.migrate else describe_runtime_storage(settings)
    print(f"cache_root={report.cache_root}")
    print(f"legacy_root={report.legacy_root}")
    print(f"cache_upload_files={report.cache_upload_files}")
    print(f"cache_export_files={report.cache_export_files}")
    print(f"legacy_upload_files={report.legacy_upload_files}")
    print(f"legacy_export_files={report.legacy_export_files}")
    print(f"missing_from_cache={report.missing_from_cache}")
    print(f"migrated_this_run={report.migrated_this_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
