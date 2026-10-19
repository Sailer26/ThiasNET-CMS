"""'Chiedi a Thias' (5d-1, D-134): si salva, parte un'email a SUPPORT_EMAIL, limite per utente."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Any

import pytest
from flask import Flask
from sqlalchemy import select

from app.extensions import db
from app.models.support import SupportRequest
from app.services import mailer, support
from tests.conftest import LoginAs
from tests.helpers import API, api_client, error_code
from tests.pages_helpers import actions, create_page

SUPPORT = f"{API}/support-requests"
THIAS = "assistenza@thiasnet.test"


@pytest.fixture
def support_app(app: Flask) -> Flask:
    app.config["SUPPORT_EMAIL"] = THIAS
    return app


def _outbox(app: Flask) -> list[EmailMessage]:
    return list(app.extensions.get(mailer.OUTBOX_KEY, []))


def _saved(app: Flask) -> list[SupportRequest]:
    with app.app_context():
        return list(db.session.execute(select(SupportRequest)).scalars())


def test_any_role_can_ask_and_thias_gets_an_email(support_app: Flask, login_as: LoginAs) -> None:
    admin, _ = login_as("admin")
    page = create_page(admin, "Orari")
    editor, user = login_as("editor")
    text = "Non riesco a cambiare la foto in alto.\nGrazie!"
    response = editor.post(SUPPORT, json={"message": text, "page_id": page["id"]})
    assert response.status_code == 201, response.get_json()
    assert response.get_json()["data"]["sent"] is True

    [mail] = _outbox(support_app)
    assert mail["To"] == THIAS
    assert mail["Reply-To"] == user.email
    body = mail.get_content()
    assert text in body and "Orari" in body and user.email in body
    assert f"/admin/pagine/{page['id']}" in body
    [saved] = _saved(support_app)
    assert saved.sent_at is not None and saved.page_id == page["id"]
    assert "support.requested" in actions(support_app)


def test_audit_never_keeps_the_text(support_app: Flask, login_as: LoginAs) -> None:
    from app.models.audit import AuditLog

    client, _ = login_as("editor")
    assert client.post(SUPPORT, json={"message": "Segreto personale"}).status_code == 201
    with support_app.app_context():
        rows = db.session.execute(select(AuditLog).where(AuditLog.action == "support.requested"))
        assert all("Segreto" not in str(row.diff_json) for row in rows.scalars())


@pytest.mark.parametrize(
    "body",
    [
        {"message": ""},
        {"message": "   "},
        {"message": "x" * (support.MESSAGE_MAX_LENGTH + 1)},
        {"message": "ok", "to": "altro@example.ch"},  # destinatario mai dal pannello
        {"message": "ok", "page_id": "uno"},
    ],
)
def test_invalid_requests_are_422(support_app: Flask, login_as: LoginAs, body: Any) -> None:
    client, _ = login_as("editor")
    assert client.post(SUPPORT, json=body).status_code == 422
    assert _outbox(support_app) == []


def test_missing_page_counts_as_no_page(support_app: Flask, login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    assert client.post(SUPPORT, json={"message": "Aiuto", "page_id": 999999}).status_code == 201
    [saved] = _saved(support_app)
    assert saved.page_id is None


def test_header_injection_in_the_text_is_harmless(support_app: Flask, login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    text = "ciao\r\nBcc: tutti@example.ch"
    assert client.post(SUPPORT, json={"message": text}).status_code == 201
    [mail] = _outbox(support_app)
    assert mail["Bcc"] is None


def test_sixth_request_in_an_hour_is_429(support_app: Flask, login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    for n in range(support.HOURLY_LIMIT):
        assert client.post(SUPPORT, json={"message": f"Domanda {n}"}).status_code == 201
    response = client.post(SUPPORT, json={"message": "Ancora"})
    assert (response.status_code, error_code(response)) == (429, "rate_limited")
    assert int(response.headers["Retry-After"]) > 0
    other, _ = login_as("admin")  # il limite è per persona
    assert other.post(SUPPORT, json={"message": "Io"}).status_code == 201


def test_without_support_email_it_is_saved_and_not_sent(app: Flask, login_as: LoginAs) -> None:
    app.config["SUPPORT_EMAIL"] = None
    client, _ = login_as("editor")
    response = client.post(SUPPORT, json={"message": "Aiuto"})
    assert response.status_code == 201
    assert response.get_json()["data"]["sent"] is False
    [saved] = _saved(app)
    assert (saved.sent_at, saved.last_error) == (None, "no_recipient")


def test_failed_email_is_retried_by_the_cli(
    support_app: Flask, login_as: LoginAs, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(message: EmailMessage) -> None:
        raise mailer.MailError("giù")

    client, _ = login_as("editor")
    monkeypatch.setattr(mailer, "send", broken)
    assert client.post(SUPPORT, json={"message": "Aiuto"}).get_json()["data"]["sent"] is False
    monkeypatch.undo()
    result = support_app.test_cli_runner().invoke(args=["send-support-requests"])
    assert result.exit_code == 0, result.output
    assert len(_outbox(support_app)) == 1
    assert _saved(support_app)[0].sent_at is not None


def test_requests_are_deleted_after_twelve_months(support_app: Flask, login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    assert client.post(SUPPORT, json={"message": "Vecchia"}).status_code == 201
    assert client.post(SUPPORT, json={"message": "Nuova"}).status_code == 201
    with support_app.app_context():
        old = db.session.execute(select(SupportRequest)).scalars().first()
        assert old is not None
        old.created_at = datetime.now(UTC) - timedelta(days=400)
        db.session.commit()
    result = support_app.test_cli_runner().invoke(args=["purge-support-requests"])
    assert result.exit_code == 0 and "1" in result.output
    assert [r.message for r in _saved(support_app)] == ["Nuova"]


def test_anonymous_cannot_ask(app: Flask) -> None:
    client = api_client(app)
    assert client.post(SUPPORT, json={"message": "x"}).status_code in {401, 403}
