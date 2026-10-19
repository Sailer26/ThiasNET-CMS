"""Messaggi del modulo contatti nel pannello (5c-2, D-126): solo amministratori e owner."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import select

from app.extensions import db
from app.models.audit import AuditLog
from app.models.contact import ContactMessage
from tests.conftest import LoginAs
from tests.helpers import API, CSRF_HEADER, error_code

MESSAGES = f"{API}/messages"


def _message(app: Flask, name: str = "Anna Rossi", **extra: Any) -> int:
    with app.app_context():
        message = ContactMessage(
            block_uid="a" * 32,
            locale="it",
            name=name,
            email=extra.pop("email", "anna@example.ch"),
            phone=extra.pop("phone", "+41 91 123 45 67"),
            message=extra.pop("message", "Buongiorno, vorrei sapere gli orari dello sportello."),
            ip_hash="h" * 64,
            **extra,
        )
        db.session.add(message)
        db.session.commit()
        return message.id


@pytest.fixture
def admin(login_as: LoginAs) -> FlaskClient:
    client, _ = login_as("admin")
    return client


def test_only_admins_and_owner_read_messages(
    app: Flask, login_as: LoginAs, api: FlaskClient
) -> None:
    _message(app)
    editor, _ = login_as("editor", can_publish=True)
    owner, _ = login_as("owner")
    assert api.get(MESSAGES).status_code == 401
    assert editor.get(MESSAGES).status_code == 403
    assert editor.get(f"{MESSAGES}/summary").status_code == 403
    assert owner.get(MESSAGES).status_code == 200


def test_list_newest_first_with_excerpt_delivery_and_expiry(app: Flask, admin: FlaskClient) -> None:
    now = datetime.now(UTC)
    first = _message(app, "Primo", created_at=now - timedelta(days=2), sent_at=now)
    second = _message(
        app,
        "Secondo",
        message="x" * 400,
        created_at=now - timedelta(days=1),
        last_error="no_recipient",
    )
    response = admin.get(MESSAGES)
    assert response.headers["Cache-Control"] == "no-store"
    body = response.get_json()
    assert [m["id"] for m in body["data"]] == [second, first]
    assert body["meta"]["total"] == 2
    latest = body["data"][0]
    assert len(latest["excerpt"]) <= 161 and "message" not in latest
    assert (latest["delivery"], latest["failure"]) == ("failed", "no_recipient")
    assert body["data"][1]["delivery"] == "sent"
    expires = datetime.fromisoformat(latest["expires_at"])
    assert timedelta(days=363) < expires - now < timedelta(days=365)
    assert latest["read_at"] is None


def test_filters_unread_and_search(app: Flask, admin: FlaskClient) -> None:
    _message(app, "Anna Rossi")
    bruno = _message(app, "Bruno Verdi", email="bruno@example.ch")
    admin.patch(f"{MESSAGES}/{bruno}", json={"read": True})
    assert [m["name"] for m in admin.get(f"{MESSAGES}?unread=1").get_json()["data"]] == [
        "Anna Rossi"
    ]
    assert [m["name"] for m in admin.get(f"{MESSAGES}?q=BRUNO").get_json()["data"]] == [
        "Bruno Verdi"
    ]
    found = [m["name"] for m in admin.get(f"{MESSAGES}?q=example.ch").get_json()["data"]]
    assert found == ["Bruno Verdi", "Anna Rossi"]
    assert admin.get(f"{MESSAGES}?q=%25").get_json()["data"] == []  # niente jolly SQL
    assert admin.get(f"{MESSAGES}/summary").get_json()["data"] == {"unread": 1, "total": 2}


def test_detail_read_unread_and_delete(app: Flask, admin: FlaskClient) -> None:
    message_id = _message(app)
    detail = admin.get(f"{MESSAGES}/{message_id}").get_json()["data"]
    assert detail["message"].startswith("Buongiorno") and detail["phone"] == "+41 91 123 45 67"
    assert admin.patch(f"{MESSAGES}/{message_id}", json={"read": True}).get_json()["data"][
        "read_at"
    ]
    unread = admin.patch(f"{MESSAGES}/{message_id}", json={"read": False}).get_json()["data"]
    assert unread["read_at"] is None
    assert admin.patch(f"{MESSAGES}/{message_id}", json={"read": "si"}).status_code == 422
    assert admin.delete(f"{MESSAGES}/{message_id}").status_code == 200
    assert admin.get(f"{MESSAGES}/{message_id}").status_code == 404
    with app.app_context():
        entry = db.session.execute(
            select(AuditLog).where(AuditLog.action == "contact_message.deleted")
        ).scalar_one()
        assert entry.entity_id == str(message_id)
        assert entry.diff_json is None  # nessun dato personale nel registro


def test_writes_need_csrf(app: Flask, admin: FlaskClient) -> None:
    message_id = _message(app)
    admin.environ_base.pop(CSRF_HEADER)
    response = admin.delete(f"{MESSAGES}/{message_id}")
    assert (response.status_code, error_code(response)) == (403, "csrf")


def test_page_of_the_form_is_shown(app: Flask, admin: FlaskClient) -> None:
    from tests.pages_helpers import create_page

    page = create_page(admin, "Contatti")
    message_id = _message(app, form_page_id=page["id"])
    data = admin.get(f"{MESSAGES}/{message_id}").get_json()["data"]
    assert data["page"] == {
        "id": page["id"],
        "title": "Contatti",
        "path": "/contatti",
        "trashed": False,
    }
