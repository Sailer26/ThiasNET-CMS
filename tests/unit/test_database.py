from __future__ import annotations

import ast
from pathlib import Path

from flask import Flask
from sqlalchemy import inspect, text

from app import create_app
from app.extensions import db

ROOT = Path(__file__).resolve().parents[2]


def _file_db_app(tmp_path: Path) -> Flask:
    uri = f"sqlite:///{(tmp_path / 'cms.db').as_posix()}"
    return create_app("testing", overrides={"SQLALCHEMY_DATABASE_URI": uri})


def test_sqlite_wal_enabled(tmp_path: Path) -> None:
    app = _file_db_app(tmp_path)
    with app.app_context():
        mode = db.session.execute(text("PRAGMA journal_mode")).scalar()
    assert mode == "wal"


def test_sqlite_foreign_keys_and_busy_timeout(tmp_path: Path) -> None:
    app = _file_db_app(tmp_path)
    with app.app_context():
        assert db.session.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert db.session.execute(text("PRAGMA busy_timeout")).scalar() == 5000


def test_migrations_upgrade_head(tmp_path: Path) -> None:
    from flask_migrate import upgrade

    app = _file_db_app(tmp_path)
    with app.app_context():
        upgrade(directory=str(ROOT / "migrations"))
        assert "alembic_version" in inspect(db.engine).get_table_names()


def test_no_create_all_in_app() -> None:
    """CLAUDE.md: mai db.create_all() fuori dai test."""
    offenders = []
    for path in (ROOT / "app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "create_all":
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders
