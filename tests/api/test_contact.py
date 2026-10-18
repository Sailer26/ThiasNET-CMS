"""Modulo contatti (D-05, D-61, D-67): token, antispam, limiti, salvataggio, invio e pulizia."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import func, select

from app.extensions import db
from app.models.contact import ContactMessage
from app.services import contact_form, mailer
from tests.conftest import LoginAs
from tests.pages_helpers import create_page, doc, publish, put_draft, uid
from tests.render_fixtures import inspect

SITE = "https://www.example.ch"
FORM_UID = uid(5)


@pytest.fixture
def contact_app(app: Flask) -> Flask:
    app.config.update(
        CONTACT_RECIPIENT="ufficio@comune.example.ch", MAIL_FROM="sito@comune.example.ch"
    )
    return app


@pytest.fixture
def page(contact_app: Flask, login_as: LoginAs) -> dict[str, Any]:
    admin, _ = login_as("admin")
    page = create_page(admin, "Contatti")
    block = {"uid": FORM_UID, "type": "contacts", "data": {"title": "Scrivici", "show_form": True}}
    put_draft(admin, page["id"], doc(title="Contatti", zones={"main": [block], "sidebar": []}))
    assert publish(admin, page["id"]).status_code == 200
    return page


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Orologio del modulo: i test lo fanno avanzare invece di aspettare."""
    now = [datetime.now(UTC).timestamp()]
    monkeypatch.setattr(contact_form, "_clock", lambda: now[0])
    return now


@pytest.fixture
def visitor(contact_app: Flask) -> FlaskClient:
    client = contact_app.test_client()
    client.environ_base["REMOTE_ADDR"] = "198.51.100.7"
    client.environ_base["HTTP_ORIGIN"] = SITE
    return client


def _token(client: FlaskClient) -> str:
    html = client.get("/contatti").get_data(as_text=True)
    found = [a["value"] for a in inspect(html).find("input") if a.get("name") == "token"]
    assert found, "il modulo deve avere il token"
    return str(found[0])


def _fields(token: str, **extra: str) -> dict[str, str]:
    return {
        "token": token,
        "name": "Maria Rossi",
        "email": "maria@example.ch",
        "phone": "+41 91 123 45 67",
        "message": "Vorrei informazioni sugli orari.",
        "website": "",
        **extra,
    }


def _send(client: FlaskClient, clock: list[float], **extra: str) -> Any:
    token = _token(client)
    clock[0] += 10  # una persona impiega più di 3 secondi a compilare
    return client.post("/_contact", data=_fields(token, **extra))


def _saved(app: Flask) -> list[ContactMessage]:
    with app.app_context():
        rows = list(db.session.execute(select(ContactMessage)).scalars())
        for row in rows:
            db.session.expunge(row)
        return rows


def _outbox(app: Flask) -> list[EmailMessage]:
    return list(app.extensions.get(mailer.OUTBOX_KEY, []))


# --- Invio riuscito -------------------------------------------------------------------


def test_message_is_saved_and_sent(
    contact_app: Flask, page: dict[str, Any], visitor: FlaskClient, clock: list[float]
) -> None:
    response = _send(visitor, clock)
    assert response.status_code == 303
    assert response.headers["Location"] == f"/contatti?contatto=inviato#contatti-{FORM_UID}"
    [row] = _saved(contact_app)
    assert (row.name, row.email, row.form_page_id, row.block_uid) == (
        "Maria Rossi",
        "maria@example.ch",
        page["id"],
        FORM_UID,
    )
    assert row.sent_at is not None
    assert len(row.ip_hash) == 64 and "198.51.100.7" not in row.ip_hash
    [mail] = _outbox(contact_app)
    assert mail["To"] == "ufficio@comune.example.ch"
    assert mail["From"] == "sito@comune.example.ch"
    assert mail["Reply-To"] == "maria@example.ch"
    assert "Vorrei informazioni" in mail.get_content()
    thanks = visitor.get(response.headers["Location"]).get_data(as_text=True)
    assert "abbiamo ricevuto il tuo messaggio" in thanks


def test_pages_with_a_form_are_never_cached(page: dict[str, Any], visitor: FlaskClient) -> None:
    assert _token(visitor) != "" and visitor.get("/contatti").headers["Cache-Control"] == "no-store"


# --- Antispam ---------------------------------------------------------------------------


def test_too_fast_or_honeypot_look_successful_but_do_nothing(
    contact_app: Flask, page: dict[str, Any], visitor: FlaskClient, clock: list[float]
) -> None:
    quick = visitor.post("/_contact", data=_fields(_token(visitor)))
    assert quick.status_code == 303
    trap = _send(visitor, clock, website="http://spam.example")
    assert trap.status_code == 303
    assert _saved(contact_app) == [] and _outbox(contact_app) == []


def test_expired_or_forged_tokens_are_rejected(
    contact_app: Flask, page: dict[str, Any], visitor: FlaskClient, clock: list[float]
) -> None:
    token = _token(visitor)
    clock[0] += 7 * 3600
    assert visitor.post("/_contact", data=_fields(token)).status_code == 422
    assert visitor.post("/_contact", data=_fields("falso.token")).status_code == 422
    assert _saved(contact_app) == []


def test_other_sites_cannot_post(
    contact_app: Flask, page: dict[str, Any], visitor: FlaskClient, clock: list[float]
) -> None:
    token = _token(visitor)
    clock[0] += 10
    visitor.environ_base["HTTP_ORIGIN"] = "https://evil.example"
    assert visitor.post("/_contact", data=_fields(token)).status_code == 403
    del visitor.environ_base["HTTP_ORIGIN"]
    assert visitor.post("/_contact", data=_fields(token)).status_code == 403


def test_oversized_body_is_413(
    page: dict[str, Any], visitor: FlaskClient, clock: list[float]
) -> None:
    assert _send(visitor, clock, message="x" * 20000).status_code == 413


# --- Validazione ------------------------------------------------------------------------


def test_invalid_fields_show_errors_and_keep_values(
    contact_app: Flask, page: dict[str, Any], visitor: FlaskClient, clock: list[float]
) -> None:
    response = _send(visitor, clock, email="non-una-email", message="")
    assert response.status_code == 422
    html = response.get_data(as_text=True)
    invalid = {
        attrs.get("name") for _, attrs in inspect(html).tags if attrs.get("aria-invalid") == "true"
    }
    assert invalid == {"email", "message"}
    assert 'value="Maria Rossi"' in html
    assert _saved(contact_app) == []


def test_header_injection_is_impossible(
    contact_app: Flask, page: dict[str, Any], visitor: FlaskClient, clock: list[float]
) -> None:
    assert _send(visitor, clock, email="a@b.ch\r\nBcc: evil@example.com").status_code == 422
    assert _send(visitor, clock, name="Maria\r\nBcc: evil@example.com").status_code == 303
    [mail] = _outbox(contact_app)
    assert "evil" not in str(mail["Bcc"] or "") and "\r\n" not in str(mail["Subject"])


# --- Limiti -----------------------------------------------------------------------------


def test_fourth_message_in_ten_minutes_is_429(
    contact_app: Flask, page: dict[str, Any], visitor: FlaskClient, clock: list[float]
) -> None:
    for _ in range(3):
        assert _send(visitor, clock).status_code == 303
    assert _send(visitor, clock).status_code == 429


def test_ipv6_neighbours_share_the_limit(
    contact_app: Flask, page: dict[str, Any], clock: list[float]
) -> None:
    def client_for(ip: str) -> FlaskClient:
        client = contact_app.test_client()
        client.environ_base.update(REMOTE_ADDR=ip, HTTP_ORIGIN=SITE)
        return client

    for n in range(3):
        assert _send(client_for(f"2001:db8:1:2::{n + 1}"), clock).status_code == 303
    assert _send(client_for("2001:db8:1:2::99"), clock).status_code == 429


# --- Email che non parte e conservazione -------------------------------------------------------


def test_failed_email_is_retried_by_the_cli(
    contact_app: Flask,
    page: dict[str, Any],
    visitor: FlaskClient,
    clock: list[float],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(_message: EmailMessage) -> None:
        raise OSError("server SMTP irraggiungibile")

    monkeypatch.setattr(mailer, "send", broken)
    assert _send(visitor, clock).status_code == 303  # il visitatore non vede il problema
    [row] = _saved(contact_app)
    assert (row.sent_at, row.send_attempts, row.last_error) == (None, 1, "send_failed")
    monkeypatch.undo()
    contact_app.config.update(
        CONTACT_RECIPIENT="ufficio@comune.example.ch", MAIL_FROM="sito@comune.example.ch"
    )
    result = contact_app.test_cli_runner().invoke(args=["send-contact-messages"])
    assert result.exit_code == 0, result.output
    [row] = _saved(contact_app)
    assert row.sent_at is not None


def test_messages_are_deleted_after_twelve_months(contact_app: Flask) -> None:
    now = datetime.now(UTC)
    with contact_app.app_context():
        for days in (400, 10):
            db.session.add(
                ContactMessage(
                    block_uid=FORM_UID,
                    locale="it",
                    name="X",
                    email="x@example.ch",
                    message="ciao",
                    ip_hash="0" * 64,
                    created_at=now - timedelta(days=days),
                )
            )
        db.session.commit()
    result = contact_app.test_cli_runner().invoke(args=["purge-contact-messages"])
    assert result.exit_code == 0
    assert re.search(r"1", result.output)
    with contact_app.app_context():
        assert (
            db.session.execute(select(func.count()).select_from(ContactMessage)).scalar_one() == 1
        )


# --- Regressioni dalla review ECC della Fase 3 -------------------------------------------


@pytest.mark.parametrize(
    "email", ["a,b@example.ch", "Capo<a@example.ch>", '"a"@example.ch', "a@exa mple.ch", "a@ü.ch"]
)
def test_only_simple_addresses_are_accepted(
    contact_app: Flask, page: dict[str, Any], visitor: FlaskClient, clock: list[float], email: str
) -> None:
    assert _send(visitor, clock, email=email).status_code == 422
    assert _outbox(contact_app) == []


def test_control_characters_in_email_are_rejected(
    page: dict[str, Any], visitor: FlaskClient, clock: list[float]
) -> None:
    assert _send(visitor, clock, email="a@example.ch" + chr(0)).status_code == 422


def test_quick_fix_after_an_error_is_not_lost(
    contact_app: Flask, page: dict[str, Any], visitor: FlaskClient, clock: list[float]
) -> None:
    failed = _send(visitor, clock, email="sbagliata")
    assert failed.status_code == 422
    token = next(
        a["value"]
        for a in inspect(failed.get_data(as_text=True)).find("input")
        if a.get("name") == "token"
    )
    fixed = visitor.post("/_contact", data=_fields(str(token)))  # corretto in meno di 3 secondi
    assert fixed.status_code == 303
    assert len(_saved(contact_app)) == 1


def test_retry_leaves_messages_still_being_sent(contact_app: Flask) -> None:
    with contact_app.app_context():
        db.session.add(
            ContactMessage(
                block_uid=FORM_UID,
                locale="it",
                name="X",
                email="x@example.ch",
                message="appena arrivato",
                ip_hash="0" * 64,
                send_attempts=1,
            )
        )
        db.session.commit()
        assert contact_form.retry_pending() == (0, 0)
