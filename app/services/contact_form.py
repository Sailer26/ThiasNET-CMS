"""Modulo contatti dei blocchi `contacts` (D-05, D-61, D-67).

Antispam senza servizi esterni: token firmato (pagina + blocco + ora), tempo minimo di
compilazione, campo trappola, limiti per IP e per sito contati sui messaggi salvati.
Il messaggio si salva prima di inviare l'email: se l'invio fallisce si ritenta dalla CLI.
"""

from __future__ import annotations

import logging
import re
import smtplib
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from enum import StrEnum
from types import MappingProxyType

from flask import current_app
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import delete, func, select

from app.extensions import db
from app.models.contact import (
    EMAIL_MAX_LENGTH,
    MESSAGE_MAX_LENGTH,
    NAME_MAX_LENGTH,
    PHONE_MAX_LENGTH,
    ContactMessage,
)
from app.models.page import Block, Page, PageStatus
from app.services import mailer, site_settings
from app.services.crypto import keyed_hash
from app.services.public_texts import text
from app.services.rate_limit import ip_bucket
from app.services.render_context import BlockView, ContactFormView, PageView
from app.services.sanitize import clean_line, clean_plain
from app.services.sql import rows_affected

log = logging.getLogger("thiasnet.contact")
ACTION = "/_contact"
TOKEN_SALT = "contact-form-v1"  # noqa: S105 (separa questi token da altri firmati, non è un segreto)
IP_PURPOSE = "contact-ip-v1"
MIN_FILL_SECONDS = 3
MAX_TOKEN_AGE = 6 * 3600
MAX_BODY_BYTES = 16 * 1024
IP_LIMITS = ((timedelta(minutes=10), 3), (timedelta(hours=24), 10))
SITE_LIMIT = (timedelta(hours=1), 50)
RETENTION = timedelta(days=365)  # D-67: 12 mesi
MAX_SEND_ATTEMPTS = 5
RETRY_WINDOW = timedelta(hours=72)
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
PHONE_RE = re.compile(r"\+?[0-9 ()./-]{3,30}")
FIELDS = ("name", "email", "phone", "message")


def _clock() -> float:
    """Ora in secondi; i test la sostituiscono per non dover aspettare."""
    return time.time()


def _now() -> datetime:
    return datetime.fromtimestamp(_clock(), UTC)


class Outcome(StrEnum):
    SENT = "sent"
    IGNORED = "ignored"  # trappola o invio troppo rapido: finto successo, nessuna traccia
    INVALID_TOKEN = "invalid_token"  # noqa: S105 (nome di un esito, non una password)
    INVALID_FIELDS = "invalid_fields"
    RATE_LIMITED = "rate_limited"


@dataclass(frozen=True)
class Submission:
    outcome: Outcome
    page: Page | None = None
    uid: str | None = None
    values: Mapping[str, str] = field(default_factory=dict)
    errors: Mapping[str, str] = field(default_factory=dict)
    retry_after: int | None = None


# --- Token --------------------------------------------------------------------------


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(str(current_app.config["SECRET_KEY"]), salt=TOKEN_SALT)


def issue_token(page_id: int, uid: str) -> str:
    return str(_serializer().dumps({"p": page_id, "b": uid, "t": int(_clock())}))


@dataclass(frozen=True)
class TokenData:
    page_id: int
    uid: str
    issued: int


def read_token(token: str) -> TokenData | None:
    try:
        data = _serializer().loads(token)
    except BadSignature:
        return None
    if not isinstance(data, dict):
        return None
    page_id, uid, issued = data.get("p"), data.get("b"), data.get("t")
    if not (isinstance(page_id, int) and isinstance(uid, str) and isinstance(issued, int)):
        return None
    if _clock() - issued > MAX_TOKEN_AGE:
        return None
    return TokenData(page_id, uid, issued)


# --- Stato del modulo per il rendering ---------------------------------------------------


def form_blocks(view: PageView) -> Sequence[BlockView]:
    return [
        block
        for blocks in view.zones.values()
        for block in blocks
        if block.type == "contacts" and block.data.get("show_form") is True
    ]


def preview_forms(view: PageView) -> Mapping[str, ContactFormView]:
    """In anteprima il modulo si vede ma non si invia (D-55)."""
    return MappingProxyType(
        {b.id: ContactFormView(action=ACTION, token="", disabled=True) for b in form_blocks(view)}
    )


def public_forms(
    view: PageView,
    *,
    sent: bool = False,
    failed: Submission | None = None,
) -> Mapping[str, ContactFormView]:
    """Un token nuovo per ogni modulo; dopo un invio con errori, valori ed errori del blocco."""
    forms = {}
    for block in form_blocks(view):
        token = issue_token(view.id or 0, block.id)
        if failed is not None and failed.uid == block.id:
            forms[block.id] = ContactFormView(
                action=ACTION,
                token=token,
                values=MappingProxyType(dict(failed.values)),
                errors=MappingProxyType(
                    {k: text(v, view.locale) for k, v in failed.errors.items()}
                ),
            )
        else:
            forms[block.id] = ContactFormView(action=ACTION, token=token, sent=sent)
    return MappingProxyType(forms)


# --- Invio ---------------------------------------------------------------------------


def _validate(form: Mapping[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    values = {
        "name": clean_line(form.get("name", "")),
        "email": form.get("email", "").strip(),
        "phone": clean_line(form.get("phone", "")),
        "message": clean_plain(form.get("message", "")),
    }
    errors: dict[str, str] = {}
    if not values["name"] or len(values["name"]) > NAME_MAX_LENGTH:
        errors["name"] = "contact_error_name"
    if len(values["email"]) > EMAIL_MAX_LENGTH or not EMAIL_RE.fullmatch(values["email"]):
        errors["email"] = "contact_error_email"
    if values["phone"] and (
        len(values["phone"]) > PHONE_MAX_LENGTH or not PHONE_RE.fullmatch(values["phone"])
    ):
        errors["phone"] = "contact_error_phone"
    if not values["message"] or len(values["message"]) > MESSAGE_MAX_LENGTH:
        errors["message"] = "contact_error_message"
    return values, errors


def _form_page(token: TokenData) -> Page | None:
    page = db.session.get(Page, token.page_id)
    if page is None or page.deleted_at is not None or page.status != PageStatus.PUBLISHED:
        return None
    block = db.session.execute(
        select(Block).where(
            Block.page_id == page.id, Block.uid == token.uid, Block.type == "contacts"
        )
    ).scalar_one_or_none()
    if block is None or (block.data_json or {}).get("show_form") is not True:
        return None
    return page


def _count_since(since: datetime, ip_hash: str | None = None) -> int:
    query = (
        select(func.count()).select_from(ContactMessage).where(ContactMessage.created_at >= since)
    )
    if ip_hash is not None:
        query = query.where(ContactMessage.ip_hash == ip_hash)
    return db.session.execute(query).scalar_one()


def _retry_after(ip_hash: str, now: datetime) -> int | None:
    """Limiti "best effort" come quelli del login (D-24): contati sui messaggi salvati."""
    for window, limit in IP_LIMITS:
        if _count_since(now - window, ip_hash) >= limit:
            return int(window.total_seconds())
    window, limit = SITE_LIMIT
    if _count_since(now - window) >= limit:
        return int(window.total_seconds())
    return None


def submit(form: Mapping[str, str], ip: str | None) -> Submission:
    token = read_token(form.get("token", ""))
    page = _form_page(token) if token is not None else None
    if token is None or page is None:
        return Submission(Outcome.INVALID_TOKEN)
    if form.get("website") or _clock() - token.issued < MIN_FILL_SECONDS:
        return Submission(Outcome.IGNORED, page=page, uid=token.uid)
    values, errors = _validate(form)
    if errors:
        return Submission(
            Outcome.INVALID_FIELDS, page=page, uid=token.uid, values=values, errors=errors
        )
    now = _now()
    ip_hash = keyed_hash(ip_bucket(ip), IP_PURPOSE)
    wait = _retry_after(ip_hash, now)
    if wait is not None:
        return Submission(Outcome.RATE_LIMITED, page=page, uid=token.uid, retry_after=wait)
    message = ContactMessage(
        form_page_id=page.id,
        block_uid=token.uid,
        locale=page.locale,
        name=values["name"],
        email=values["email"],
        phone=values["phone"] or None,
        message=values["message"],
        ip_hash=ip_hash,
        created_at=now,
    )
    db.session.add(message)
    db.session.commit()  # salvato prima dell'invio: un errore SMTP non perde il messaggio
    deliver(message, page_title=page.title)
    return Submission(Outcome.SENT, page=page, uid=token.uid)


# --- Email ----------------------------------------------------------------------------


def _email(message: ContactMessage, recipient: str, page_title: str) -> EmailMessage:
    settings = site_settings.current()
    email = EmailMessage()
    email["From"] = current_app.config.get("MAIL_FROM") or recipient
    email["To"] = recipient
    email["Reply-To"] = message.email  # validato: niente a capo, quindi niente intestazioni in più
    email["Subject"] = f"Nuovo messaggio dal sito {settings.name}"
    email.set_content(
        f"Nuovo messaggio dal modulo contatti della pagina “{page_title}”.\n\n"
        f"Nome: {message.name}\n"
        f"Email: {message.email}\n"
        f"Telefono: {message.phone or '-'}\n\n"
        f"{message.message}\n\n"
        f"Per rispondere usa “Rispondi”: il messaggio va direttamente a chi ha scritto.\n"
    )
    return email


def deliver(message: ContactMessage, *, page_title: str) -> bool:
    recipient = site_settings.current().contact_recipient
    if not recipient:
        log.warning(
            "CONTACT_RECIPIENT non impostato: messaggio %s salvato ma non inviato", message.id
        )
        message.last_error = "no_recipient"
        db.session.commit()
        return False
    message.send_attempts += 1
    try:
        mailer.send(_email(message, recipient, page_title))
    except (OSError, smtplib.SMTPException, mailer.MailError):
        log.exception("invio del messaggio di contatto %s non riuscito", message.id)
        message.last_error = "send_failed"
        db.session.commit()
        return False
    message.sent_at, message.last_error = _now(), None
    db.session.commit()
    return True


def retry_pending() -> tuple[int, int]:
    """Messaggi non ancora inviati negli ultimi 3 giorni, al massimo 5 tentativi ciascuno."""
    query = select(ContactMessage).where(
        ContactMessage.sent_at.is_(None),
        ContactMessage.send_attempts < MAX_SEND_ATTEMPTS,
        ContactMessage.created_at >= _now() - RETRY_WINDOW,
    )
    sent = failed = 0
    for message in list(db.session.execute(query).scalars()):
        page = db.session.get(Page, message.form_page_id) if message.form_page_id else None
        if deliver(message, page_title=page.title if page else "-"):
            sent += 1
        else:
            failed += 1
    return sent, failed


def purge_expired() -> int:
    """D-67: i messaggi più vecchi di 12 mesi si cancellano."""
    statement = delete(ContactMessage).where(ContactMessage.created_at < _now() - RETENTION)
    removed = rows_affected(statement)
    db.session.commit()
    return removed
