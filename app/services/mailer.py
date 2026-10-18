"""Invio delle email del sito (D-05, D-61).

Backend da configurazione (`MAIL_BACKEND`): `smtp` in produzione (cifrato, timeout 10 s),
`console` in sviluppo (solo log), `memory` nei test (lista in `app.extensions`).
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app

log = logging.getLogger("thiasnet.mail")
OUTBOX_KEY = "thiasnet.outbox"
SMTP_TIMEOUT = 10


class MailError(RuntimeError):
    """Email non inviata (configurazione mancante o server irraggiungibile)."""


def _smtp(message: EmailMessage) -> None:
    config = current_app.config
    host = config.get("SMTP_HOST")
    if not host:
        raise MailError("SMTP_HOST mancante")
    port, security = int(config["SMTP_PORT"]), str(config["SMTP_SECURITY"])
    context = ssl.create_default_context()
    connection: smtplib.SMTP = (
        smtplib.SMTP_SSL(host, port, timeout=SMTP_TIMEOUT, context=context)
        if security == "ssl"
        else smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT)
    )
    with connection as smtp:
        if security == "starttls":
            smtp.starttls(context=context)
        if config.get("SMTP_USER"):
            smtp.login(str(config["SMTP_USER"]), str(config.get("SMTP_PASSWORD") or ""))
        smtp.send_message(message)


def send(message: EmailMessage) -> None:
    backend = current_app.config["MAIL_BACKEND"]
    if backend == "smtp":
        _smtp(message)
    elif backend == "memory":
        current_app.extensions.setdefault(OUTBOX_KEY, []).append(message)
    else:  # console: in sviluppo il messaggio si legge nel log
        log.info("Email (non inviata) a %s: %s", message["To"], message["Subject"])
