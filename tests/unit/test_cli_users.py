"""Comandi CLI per owner e recupero accesso (D-29, D-31)."""

from __future__ import annotations

from flask import Flask
from sqlalchemy import select

from app.extensions import db
from app.models.audit import AuditLog
from app.models.user import User
from tests.helpers import api_client, login, make_user

STRONG = "Password-owner-sicura-1"


def _run(app: Flask, args: list[str], answers: str = "") -> tuple[int, str]:
    result = app.test_cli_runner().invoke(args=args, input=answers)
    return result.exit_code, result.output


def test_create_owner_with_hidden_confirmed_password(app: Flask) -> None:
    code, output = _run(
        app, ["create-owner", "--email", "Thias@Example.ch"], f"{STRONG}\n{STRONG}\n"
    )
    assert code == 0, output
    assert STRONG not in output
    with app.app_context():
        owner = db.session.execute(select(User)).scalar_one()
        assert owner.email == "thias@example.ch"
        assert owner.role == "owner"
        actions = db.session.execute(select(AuditLog.action)).scalars().all()
        assert actions == ["user.created"]
    assert login(api_client(app), "thias@example.ch", STRONG).status_code == 200


def test_create_owner_rejects_weak_password(app: Flask) -> None:
    code, output = _run(app, ["create-owner", "--email", "t@example.ch"], "corta\ncorta\n")
    assert code != 0
    assert "12" in output


def test_second_owner_needs_flag(app: Flask) -> None:
    make_user(app, "primo@example.ch", "owner")
    code, output = _run(app, ["create-owner", "--email", "t@example.ch"], f"{STRONG}\n{STRONG}\n")
    assert code != 0
    assert "--additional" in output
    code, _ = _run(
        app, ["create-owner", "--email", "t@example.ch", "--additional"], f"{STRONG}\n{STRONG}\n"
    )
    assert code == 0


def test_create_owner_rejects_existing_email(app: Flask) -> None:
    make_user(app, "t@example.ch", "editor")
    code, output = _run(app, ["create-owner", "--email", "t@example.ch"], f"{STRONG}\n{STRONG}\n")
    assert code != 0
    assert "esiste già" in output.lower()


def test_set_password(app: Flask) -> None:
    make_user(app, "t@example.ch", "owner")
    code, _ = _run(app, ["set-password", "--email", "t@example.ch"], f"{STRONG}\n{STRONG}\n")
    assert code == 0
    assert login(api_client(app), "t@example.ch", STRONG).status_code == 200


def test_disable_totp(app: Flask) -> None:
    user = make_user(app, "t@example.ch", "owner")
    with app.app_context():
        db.session.get_one(User, user.id).totp_secret_enc = "cifrato"
        db.session.commit()
    code, _ = _run(app, ["disable-totp", "--email", "t@example.ch"])
    assert code == 0
    with app.app_context():
        assert db.session.get_one(User, user.id).totp_secret_enc is None


def test_unknown_email_in_cli(app: Flask) -> None:
    code, output = _run(app, ["disable-totp", "--email", "nessuno@example.ch"])
    assert code != 0
    assert "non trovato" in output
