from __future__ import annotations

from _pytest.monkeypatch import MonkeyPatch
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from novel_analyzer.database.session import create_schema


def patch_cli_sqlite_runtime(
    monkeypatch: MonkeyPatch,
) -> tuple[Engine, sessionmaker[Session], str]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr(
        "novel_analyzer.cli.app.create_session_factory",
        lambda settings=None: factory,
    )
    monkeypatch.setattr(
        "novel_analyzer.cli.app.ensure_database_exists",
        lambda settings=None: None,
    )
    monkeypatch.setattr(
        "novel_analyzer.cli.app.upgrade_database",
        lambda settings=None: None,
    )
    db_url = "postgresql+psycopg://novel:novelpass@127.0.0.1:5432/test"
    return engine, factory, db_url
