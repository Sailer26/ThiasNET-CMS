from __future__ import annotations

from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask import Flask
from flask_migrate import upgrade
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from app.models import Base
from app.models.user import User

ROOT = Path(__file__).resolve().parents[2]


def test_migrations_match_models(tmp_path: Path) -> None:
    """Le migrazioni Alembic producono esattamente lo schema dei modelli."""
    uri = f"sqlite:///{(tmp_path / 'cms.db').as_posix()}"
    app = create_app("testing", overrides={"SQLALCHEMY_DATABASE_URI": uri})
    with app.app_context():
        upgrade(directory=str(ROOT / "migrations"))
        with db.engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            assert compare_metadata(context, Base.metadata) == []


def _user(email: str, role: str = "editor") -> User:
    return User(email=email, password_hash="x", role=role)


def test_role_check_constraint(app: Flask) -> None:
    with app.app_context():
        db.session.add(_user("a@example.ch", role="superuser"))
        with pytest.raises(IntegrityError):
            db.session.commit()


def test_email_unique(app: Flask) -> None:
    with app.app_context():
        db.session.add_all([_user("a@example.ch"), _user("a@example.ch")])
        with pytest.raises(IntegrityError):
            db.session.commit()


def test_user_defaults(app: Flask) -> None:
    with app.app_context():
        user = _user("a@example.ch")
        db.session.add(user)
        db.session.commit()
        assert user.active is True
        assert user.can_publish is False
        assert user.session_version == 1
        assert user.totp_secret_enc is None
        assert user.tour_completed_at is None
        assert user.created_at.tzinfo is not None
        assert user.get_id() == f"{user.id}:1"
