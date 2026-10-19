"""Messaggi del modulo contatti nel pannello (D-126): elenco, lettura, letto/da leggere,
eliminazione. Solo chi ha `messages.view` (amministratori e owner).

Il registro attività non contiene mai i dati dei visitatori: solo l'id del messaggio.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select

from app.extensions import db
from app.models.contact import ContactMessage
from app.models.page import Page
from app.models.types import utcnow
from app.models.user import User
from app.services import audit
from app.services.contact_form import RETENTION
from app.services.errors import not_found

EXCERPT_LENGTH = 160


def _search(query: Any, q: str | None) -> Any:
    if not q:
        return query
    needle = q.strip().lower()
    return query.where(
        or_(
            func.lower(ContactMessage.name).contains(needle, autoescape=True),
            func.lower(ContactMessage.email).contains(needle, autoescape=True),
        )
    )


def list_messages(
    *, q: str | None, unread: bool, page_no: int, limit: int
) -> tuple[list[ContactMessage], int]:
    query = _search(select(ContactMessage), q)
    if unread:
        query = query.where(ContactMessage.read_at.is_(None))
    total = db.session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = db.session.execute(
        query.order_by(ContactMessage.created_at.desc(), ContactMessage.id.desc())
        .offset((page_no - 1) * limit)
        .limit(limit)
    )
    return list(rows.scalars()), int(total)


def summary() -> dict[str, int]:
    total = db.session.execute(select(func.count(ContactMessage.id))).scalar_one()
    unread = db.session.execute(
        select(func.count(ContactMessage.id)).where(ContactMessage.read_at.is_(None))
    ).scalar_one()
    return {"unread": int(unread), "total": int(total)}


def get_message(message_id: int) -> ContactMessage:
    message = db.session.get(ContactMessage, message_id)
    if message is None:
        raise not_found("Messaggio non trovato")
    return message


def set_read(message: ContactMessage, read: bool) -> ContactMessage:
    """Stato comune a tutti (D-126): non serve audit, non cambia contenuti."""
    message.read_at = (message.read_at or utcnow()) if read else None
    db.session.commit()
    return message


def delete_message(actor: User, message: ContactMessage) -> None:
    audit.record(
        "contact_message.deleted", actor_id=actor.id, entity="contact_message", entity_id=message.id
    )
    db.session.delete(message)
    db.session.commit()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _delivery(message: ContactMessage) -> str:
    if message.sent_at is not None:
        return "sent"
    return "failed" if message.last_error else "pending"


def _page(message: ContactMessage, pages: dict[int, Page]) -> dict[str, Any] | None:
    page = pages.get(message.form_page_id) if message.form_page_id is not None else None
    if page is None:
        return None
    return {
        "id": page.id,
        "title": page.title,
        "path": page.path,
        "trashed": page.deleted_at is not None,
    }


def _pages_of(messages: list[ContactMessage]) -> dict[int, Page]:
    ids = {m.form_page_id for m in messages if m.form_page_id is not None}
    if not ids:
        return {}
    return {p.id: p for p in db.session.execute(select(Page).where(Page.id.in_(ids))).scalars()}


def _base(message: ContactMessage, pages: dict[int, Page]) -> dict[str, Any]:
    return {
        "id": message.id,
        "name": message.name,
        "email": message.email,
        "phone": message.phone,
        "locale": message.locale,
        "page": _page(message, pages),
        "created_at": _iso(message.created_at),
        "read_at": _iso(message.read_at),
        "delivery": _delivery(message),
        "failure": message.last_error if message.sent_at is None else None,
        "expires_at": _iso(message.created_at + RETENTION),
    }


def serialize_list(messages: list[ContactMessage]) -> list[dict[str, Any]]:
    pages = _pages_of(messages)
    result = []
    for message in messages:
        text = " ".join(message.message.split())
        excerpt = text if len(text) <= EXCERPT_LENGTH else text[: EXCERPT_LENGTH - 1] + "…"
        result.append({**_base(message, pages), "excerpt": excerpt})
    return result


def serialize_one(message: ContactMessage) -> dict[str, Any]:
    return {**_base(message, _pages_of([message])), "message": message.message}
