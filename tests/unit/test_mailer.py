"""Invio email (D-61): SMTP cifrato con timeout, console in sviluppo, memoria nei test."""

from __future__ import annotations

import logging
from email.message import EmailMessage
from typing import Any, ClassVar

import pytest
from flask import Flask

from app.services import mailer


class FakeSMTP:
    calls: ClassVar[list[tuple[str, Any]]] = []

    def __init__(self, host: str, port: int, timeout: float) -> None:
        FakeSMTP.calls = [("connect", (host, port, timeout))]

    def __enter__(self) -> FakeSMTP:
        return self

    def __exit__(self, *_exc: object) -> None:
        FakeSMTP.calls.append(("quit", None))

    def starttls(self, context: Any = None) -> None:
        FakeSMTP.calls.append(("starttls", context is not None))

    def login(self, user: str, password: str) -> None:
        FakeSMTP.calls.append(("login", user))

    def send_message(self, message: EmailMessage) -> None:
        FakeSMTP.calls.append(("send", message["To"]))


def _message() -> EmailMessage:
    message = EmailMessage()
    message["To"] = "ufficio@example.ch"
    message["From"] = "sito@example.ch"
    message["Subject"] = "Prova"
    message.set_content("ciao")
    return message


def test_smtp_uses_starttls_login_and_timeout(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)
    app.config.update(
        MAIL_BACKEND="smtp", SMTP_HOST="mail.example.ch", SMTP_USER="sito", SMTP_PASSWORD="segreta"
    )
    with app.app_context():
        mailer.send(_message())
    assert FakeSMTP.calls == [
        ("connect", ("mail.example.ch", 587, mailer.SMTP_TIMEOUT)),
        ("starttls", True),
        ("login", "sito"),
        ("send", "ufficio@example.ch"),
        ("quit", None),
    ]


def test_smtp_without_host_is_an_error(app: Flask) -> None:
    app.config.update(MAIL_BACKEND="smtp", SMTP_HOST=None)
    with app.app_context(), pytest.raises(mailer.MailError):
        mailer.send(_message())


def test_memory_backend_collects_messages(app: Flask) -> None:
    with app.app_context():
        mailer.send(_message())
    assert [m["To"] for m in app.extensions[mailer.OUTBOX_KEY]] == ["ufficio@example.ch"]


def test_console_backend_only_logs(app: Flask, caplog: pytest.LogCaptureFixture) -> None:
    app.config.update(MAIL_BACKEND="console")
    caplog.set_level(logging.INFO, logger="thiasnet.mail")
    with app.app_context():
        mailer.send(_message())
    assert "ufficio@example.ch" in caplog.text
