from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novel_analyzer.database.session import create_schema
from tests.test_whole_book_imitation_service import _seed_branch


def test_bootstrap_weitu_validation_workspace_exports_artifacts(tmp_path: Path, monkeypatch) -> None:
    from scripts import bootstrap_weitu_validation_workspace as bootstrap

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        session.commit()

    target_root = tmp_path / "manual_eval"
    template_dir = target_root / "_template"
    (template_dir / "artifacts").mkdir(parents=True)
    (template_dir / "exports").mkdir(parents=True)
    (template_dir / "notes").mkdir(parents=True)
    (template_dir / "README.md").write_text("# template\n", encoding="utf-8")
    (template_dir / "notes" / "manual-review-notes.md").write_text("# 人工审查笔记\n", encoding="utf-8")
    (template_dir / "notes" / "next-actions.md").write_text("# 后续行动\n", encoding="utf-8")
    (template_dir / "notes" / "problem-trace.md").write_text("# 问题追踪\n", encoding="utf-8")

    monkeypatch.setattr(bootstrap, "TARGET_ROOT", target_root)
    monkeypatch.setattr(bootstrap, "TEMPLATE_DIR", template_dir)
    monkeypatch.setattr(bootstrap, "create_session_factory", lambda settings=None: factory)

    assert bootstrap.main([branch_id, "weitu-test-workspace"]) == 0

    workspace = target_root / "weitu-test-workspace"
    assert workspace.exists()
    assert (workspace / "artifacts" / "weitu-branch-bundle.json").exists()
    assert (workspace / "artifacts" / "weitu-whole-book-report.json").exists()
    assert (workspace / "exports" / "weitu-branch-report.md").exists()
    assert (workspace / "notes" / "manual-review-notes.md").exists()
    report_text = (workspace / "artifacts" / "weitu-whole-book-report.json").read_text(encoding="utf-8")
    assert "session_loom_signals" in report_text
    assert "session_loom_gate_summary" in report_text
