"""Matrice dei permessi (D-31, D-32, D-33): owner > admin > editor."""

from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from sqlalchemy import select

from app.extensions import db
from app.models.audit import AuditLog
from app.models.user import User
from tests.conftest import LoginAs
from tests.helpers import API, ME_URL, PASSWORD, api_client, login, make_user

USERS = f"{API}/users"
NEW_PASSWORD = "Password-nuova-123"


def _new(email: str, role: str = "editor", **extra: Any) -> dict[str, Any]:
    return {"email": email, "password": NEW_PASSWORD, "role": role, **extra}


# --- Accesso --------------------------------------------------------------


def test_users_endpoints_require_login(api: Any) -> None:
    assert api.get(USERS).status_code == 401
    assert api.post(USERS, json=_new("x@example.ch")).status_code == 401


def test_editor_cannot_manage_users(login_as: LoginAs) -> None:
    editor, _ = login_as("editor")
    assert editor.get(USERS).status_code == 403
    assert editor.post(USERS, json=_new("x@example.ch")).status_code == 403


# --- Elenco ---------------------------------------------------------------


def test_admin_sees_only_editors_and_self(app: Flask, login_as: LoginAs) -> None:
    make_user(app, "owner@example.ch", "owner")
    make_user(app, "altro-admin@example.ch", "admin")
    make_user(app, "ed@example.ch", "editor")
    admin, me = login_as("admin")
    body = admin.get(USERS).get_json()
    emails = {u["email"] for u in body["data"]}
    assert emails == {"ed@example.ch", me.email}
    assert body["meta"]["total"] == 2


def test_owner_sees_everyone(app: Flask, login_as: LoginAs) -> None:
    make_user(app, "admin@example.ch", "admin")
    make_user(app, "ed@example.ch", "editor")
    owner, _ = login_as("owner")
    assert owner.get(USERS).get_json()["meta"]["total"] == 3


def test_list_limit_is_bounded(login_as: LoginAs) -> None:
    owner, _ = login_as("owner")
    assert owner.get(f"{USERS}?limit=101").status_code == 422
    assert owner.get(f"{USERS}?page=0").status_code == 422


# --- Creazione ------------------------------------------------------------


def test_admin_creates_editor(app: Flask, login_as: LoginAs) -> None:
    admin, me = login_as("admin")
    response = admin.post(USERS, json=_new("Nuovo@Example.ch", can_publish=True))
    assert response.status_code == 201
    created = response.get_json()["data"]
    assert created["email"] == "nuovo@example.ch"
    assert created["can_publish"] is True
    assert login(api_client(app), "nuovo@example.ch", NEW_PASSWORD).status_code == 200
    with app.app_context():
        entry = db.session.execute(
            select(AuditLog).where(AuditLog.action == "user.created")
        ).scalar_one()
        assert entry.user_id == me.id
        assert NEW_PASSWORD not in str(entry.diff_json)
        assert "password" not in str(entry.diff_json)


def test_admin_cannot_create_admin(login_as: LoginAs) -> None:
    admin, _ = login_as("admin")
    assert admin.post(USERS, json=_new("x@example.ch", "admin")).status_code == 403


def test_owner_creates_admin(login_as: LoginAs) -> None:
    owner, _ = login_as("owner")
    assert owner.post(USERS, json=_new("x@example.ch", "admin")).status_code == 201


def test_nobody_creates_owner_via_api(login_as: LoginAs) -> None:
    owner, _ = login_as("owner")
    assert owner.post(USERS, json=_new("x@example.ch", "owner")).status_code == 422


def test_duplicate_email_is_409(app: Flask, login_as: LoginAs) -> None:
    make_user(app, "ed@example.ch")
    admin, _ = login_as("admin")
    assert admin.post(USERS, json=_new("ED@example.ch")).status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "non-una-email", "password": NEW_PASSWORD, "role": "editor"},
        {"email": "x@example.ch", "password": "corta", "role": "editor"},
        {"email": "x@example.ch", "password": NEW_PASSWORD, "role": "editor", "is_admin": True},
    ],
)
def test_invalid_payload_is_422(login_as: LoginAs, payload: dict[str, Any]) -> None:
    admin, _ = login_as("admin")
    assert admin.post(USERS, json=payload).status_code == 422


# --- Modifica -------------------------------------------------------------


def test_admin_cannot_touch_admin_or_owner(app: Flask, login_as: LoginAs) -> None:
    other_admin = make_user(app, "a2@example.ch", "admin")
    owner = make_user(app, "o@example.ch", "owner")
    admin, _ = login_as("admin")
    for target in (other_admin, owner):
        assert admin.get(f"{USERS}/{target.id}").status_code == 403
        assert admin.patch(f"{USERS}/{target.id}", json={"active": False}).status_code == 403


def test_admin_deactivates_editor_and_kills_sessions(app: Flask, login_as: LoginAs) -> None:
    editor_client, editor = login_as("editor")
    admin, _ = login_as("admin")
    response = admin.patch(f"{USERS}/{editor.id}", json={"active": False})
    assert response.status_code == 200
    assert response.get_json()["data"]["active"] is False
    assert editor_client.get(ME_URL).status_code == 401
    assert login(api_client(app), editor.email).status_code == 401


def test_admin_resets_editor_password(app: Flask, login_as: LoginAs) -> None:
    _, editor = login_as("editor")
    admin, _ = login_as("admin")
    patch = admin.patch(f"{USERS}/{editor.id}", json={"password": NEW_PASSWORD})
    assert patch.status_code == 200
    assert login(api_client(app), editor.email, NEW_PASSWORD).status_code == 200
    assert login(api_client(app, ip="203.0.113.50"), editor.email, PASSWORD).status_code == 401


def test_admin_toggles_can_publish(login_as: LoginAs) -> None:
    editor_client, editor = login_as("editor")
    admin, _ = login_as("admin")
    assert admin.patch(f"{USERS}/{editor.id}", json={"can_publish": True}).status_code == 200
    assert "content.publish" in editor_client.get(ME_URL).get_json()["data"]["permissions"]


def test_nobody_deactivates_or_demotes_self(login_as: LoginAs) -> None:
    owner, me = login_as("owner")
    assert owner.patch(f"{USERS}/{me.id}", json={"active": False}).status_code == 403
    assert owner.patch(f"{USERS}/{me.id}", json={"role": "editor"}).status_code == 403


def test_owner_changes_role_and_it_is_audited(app: Flask, login_as: LoginAs) -> None:
    _, editor = login_as("editor")
    owner, _ = login_as("owner")
    response = owner.patch(f"{USERS}/{editor.id}", json={"role": "admin"})
    assert response.status_code == 200
    with app.app_context():
        entry = db.session.execute(
            select(AuditLog).where(AuditLog.action == "user.updated")
        ).scalar_one()
        assert entry.diff_json == {"role": ["editor", "admin"]}


def test_admin_cannot_promote(login_as: LoginAs) -> None:
    _, editor = login_as("editor")
    admin, _ = login_as("admin")
    assert admin.patch(f"{USERS}/{editor.id}", json={"role": "admin"}).status_code == 403


def test_role_owner_via_patch_is_422(login_as: LoginAs) -> None:
    _, editor = login_as("editor")
    owner, _ = login_as("owner")
    assert owner.patch(f"{USERS}/{editor.id}", json={"role": "owner"}).status_code == 422


def test_missing_user_is_404(login_as: LoginAs) -> None:
    owner, _ = login_as("owner")
    assert owner.get(f"{USERS}/9999").status_code == 404


def test_admin_resets_editor_totp(app: Flask, login_as: LoginAs) -> None:
    _, editor = login_as("editor")
    with app.app_context():
        db.session.get_one(User, editor.id).totp_secret_enc = "cifrato"
        db.session.commit()
    admin, _ = login_as("admin")
    assert admin.post(f"{USERS}/{editor.id}/totp/reset").status_code == 200
    with app.app_context():
        assert db.session.get_one(User, editor.id).totp_secret_enc is None


# --- Audit ----------------------------------------------------------------


def test_only_owner_reads_audit(login_as: LoginAs) -> None:
    admin, _ = login_as("admin")
    owner, _ = login_as("owner")
    assert admin.get(f"{API}/audit").status_code == 403
    body = owner.get(f"{API}/audit").get_json()
    assert body["meta"]["total"] >= 2
    entry = body["data"][0]
    assert set(entry) >= {"id", "action", "user_id", "created_at"}
    assert "ip_hash" not in entry
