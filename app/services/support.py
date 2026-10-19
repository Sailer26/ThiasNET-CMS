"""'Chiedi a Thias' (D-09, D-134).

La richiesta si salva prima dell'invio (come i messaggi del modulo contatti): se l'email non
parte la ritenta `flask send-support-requests`. Il destinatario è solo `SUPPORT_EMAIL` della
configurazione; il pannello non sceglie né indirizzi né intestazioni. Il registro attività
non conserva il testo. Si cancellano dopo 12 mesi (`flask purge-support-requests`).
"""

from __future__ import annotations

import email.policy
import logging
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from flask import current_app
from sqlalchemy import delete, func, or_, select

from app.extensions import db
from app.models.page import Page
from app.models.support import SCREEN_MAX_LENGTH, SupportRequest
from app.models.user import User
from app.services import audit, mailer, site_settings
from app.services.contact_form import SEND_ERRORS
from app.services.errors import ServiceError
from app.services.public_pages import public_url
from app.services.sanitize import clean_line, clean_plain
from app.services.sql import rows_affected
from app.services.theme import active_theme

log = logging.getLogger("thiasnet.support")
MESSAGE_MAX_LENGTH = 2000
HOURLY_LIMIT = 5
DAILY_LIMIT = 20
RETENTION = timedelta(days=365)
MAX_SEND_ATTEMPTS = 5
RETRY_WINDOW = timedelta(hours=72)
RETRY_GRACE = timedelta(minutes=10)  # la richiesta che l'ha salvata la sta ancora inviando
ROLE_LABELS = {"owner": "ThiasNET", "admin": "amministratore", "editor": "editor"}


def _now() -> datetime:
    return datetime.now(UTC)


def _wait_seconds(user_id: int, now: datetime) -> int | None:
    """Secondi da aspettare se la persona ha già chiesto troppo (5 all'ora, 20 al giorno)."""
    for window, limit in ((timedelta(hours=1), HOURLY_LIMIT), (timedelta(days=1), DAILY_LIMIT)):
        since = now - window
        query = select(func.count(), func.min(SupportRequest.created_at)).where(
            SupportRequest.user_id == user_id, SupportRequest.created_at >= since
        )
        count, oldest = db.session.execute(query).one()
        if count >= limit and oldest is not None:
            oldest = oldest if oldest.tzinfo else oldest.replace(tzinfo=UTC)
            return max(1, int((oldest + window - now).total_seconds()))
    return None


def _email(request: SupportRequest, user: User | None, page: Page | None) -> EmailMessage:
    config = current_app.config
    site = config.get("SITE_URL") or ""
    recipient = str(config["SUPPORT_EMAIL"])
    sender = clean_line(user.email) if user else "-"
    role = ROLE_LABELS.get(user.role, user.role) if user else "-"
    mail = EmailMessage(policy=email.policy.SMTP)
    mail["From"] = config.get("MAIL_FROM") or recipient
    mail["To"] = recipient
    if user:
        mail["Reply-To"] = sender  # email dell'account, già validata alla creazione
    mail["Subject"] = f"Chiedi a Thias: {clean_line(site_settings.current().name)}"
    where = "-"
    if page is not None:
        where = (
            f"{page.title}\n  Nel pannello: {site}/admin/pagine/{page.id}"
            f"\n  Sul sito: {site}{public_url(page, active_theme())}"
        )
    mail.set_content(
        f"Richiesta di assistenza dal sito {clean_line(site_settings.current().name)} ({site}).\n\n"
        f"Da: {sender} ({role})\n"
        f"Pagina: {where}\n"
        f"Schermata: {request.screen or '-'}\n\n"
        f"{request.message}\n\n"
        "Per rispondere usa «Rispondi»: il messaggio va direttamente al cliente.\n"
    )
    return mail


def deliver(request: SupportRequest) -> bool:
    if not current_app.config.get("SUPPORT_EMAIL"):
        log.warning("SUPPORT_EMAIL non impostato: richiesta %s salvata, non inviata", request.id)
        request.last_error = "no_recipient"
        db.session.commit()
        return False
    user = db.session.get(User, request.user_id) if request.user_id else None
    page = db.session.get(Page, request.page_id) if request.page_id else None
    request.send_attempts += 1
    db.session.commit()  # il tentativo conta anche se l'invio fa cadere il processo
    try:
        mailer.send(_email(request, user, page))
    except SEND_ERRORS:
        log.exception("invio della richiesta di assistenza %s non riuscito", request.id)
        request.last_error = "send_failed"
        db.session.commit()
        return False
    request.sent_at, request.last_error = _now(), None
    db.session.commit()
    return True


def submit(
    user: User, message: str, page_id: int | None, screen: str
) -> tuple[SupportRequest, bool]:
    text = clean_plain(message)
    if not text:
        raise ServiceError("invalid_message", "Scrivi che cosa ti serve", 422)
    if len(text) > MESSAGE_MAX_LENGTH:
        raise ServiceError("invalid_message", f"Al massimo {MESSAGE_MAX_LENGTH} caratteri", 422)
    now = _now()
    wait = _wait_seconds(user.id, now)
    if wait is not None:
        raise ServiceError(
            "rate_limited",
            "Hai già scritto diverse volte: Thias ti risponde appena può. Riprova più tardi.",
            429,
            retry_after=wait,
        )
    page = db.session.get(Page, page_id) if page_id is not None else None
    request = SupportRequest(
        user_id=user.id,
        page_id=page.id if page is not None and page.deleted_at is None else None,
        screen=clean_line(screen)[:SCREEN_MAX_LENGTH],
        message=text,
        created_at=now,
    )
    db.session.add(request)
    db.session.flush()
    audit.record(
        "support.requested", actor_id=user.id, entity="support_request", entity_id=request.id
    )
    db.session.commit()
    return request, deliver(request)


def retry_pending() -> tuple[int, int]:
    """Come i messaggi: ultimi 3 giorni, al massimo 5 tentativi, non quelli appena salvati."""
    now = _now()
    query = select(SupportRequest).where(
        SupportRequest.sent_at.is_(None),
        SupportRequest.send_attempts < MAX_SEND_ATTEMPTS,
        SupportRequest.created_at >= now - RETRY_WINDOW,
        or_(
            SupportRequest.last_error.is_not(None),
            SupportRequest.created_at < now - RETRY_GRACE,
        ),
    )
    sent = failed = 0
    for request in list(db.session.execute(query).scalars()):
        if deliver(request):
            sent += 1
        else:
            failed += 1
    return sent, failed


def purge_expired() -> int:
    statement = delete(SupportRequest).where(SupportRequest.created_at < _now() - RETENTION)
    removed = rows_affected(statement)
    db.session.commit()
    return removed
