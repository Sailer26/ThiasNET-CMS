"""Registro delle attività. La riga viene aggiunta alla sessione: la salva il commit di chi
fa la modifica, così modifica e audit stanno nella stessa transazione."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from flask import has_request_context, request
from sqlalchemy import func, or_, select

from app.extensions import db
from app.models.audit import AuditLog
from app.services.crypto import hash_ip

SENSITIVE_KEY_RE = re.compile(r"password|secret|token|hash", re.IGNORECASE)


def _redact(value: Any) -> Any:
    """Toglie ricorsivamente le chiavi sensibili: nell'audit non finiscono mai segreti."""
    if isinstance(value, Mapping):
        return {k: _redact(v) for k, v in value.items() if not SENSITIVE_KEY_RE.search(str(k))}
    if isinstance(value, list | tuple):
        return [_redact(v) for v in value]
    return value


def record(
    action: str,
    *,
    actor_id: int | None,
    entity: str | None = None,
    entity_id: int | str | None = None,
    diff: Mapping[str, Any] | None = None,
) -> AuditLog:
    ip = request.remote_addr if has_request_context() else None
    entry = AuditLog(
        user_id=actor_id,
        action=action,
        entity=entity,
        entity_id=None if entity_id is None else str(entity_id),
        diff_json=_redact(diff) if diff else None,
        ip_hash=hash_ip(ip),
    )
    db.session.add(entry)
    return entry


# Tipi di azione per i filtri: prefissi fissi, mai testo libero in un LIKE.
CATEGORIES: Mapping[str, tuple[str, ...]] = {
    "pages": ("page.",),
    "media": ("media.", "media_folder."),
    "users": ("user.",),
    "access": ("auth.",),
    "totp": ("totp.",),
    "messages": ("contact_message.",),
}
ENTITIES = frozenset({"page", "media", "media_folder", "user", "contact_message"})


@dataclass(frozen=True)
class AuditFilter:
    user_id: int | None = None
    category: str | None = None
    entity: str | None = None
    entity_id: str | None = None
    since: datetime | None = None
    until: datetime | None = None


def list_entries(
    page: int, limit: int, where: AuditFilter | None = None
) -> tuple[list[AuditLog], int]:
    query = select(AuditLog)
    f = where or AuditFilter()
    if f.user_id is not None:
        query = query.where(AuditLog.user_id == f.user_id)
    if f.category is not None:
        query = query.where(or_(*(AuditLog.action.startswith(p) for p in CATEGORIES[f.category])))
    if f.entity is not None:
        query = query.where(AuditLog.entity == f.entity, AuditLog.entity_id == f.entity_id)
    if f.since is not None:
        query = query.where(AuditLog.created_at >= f.since)
    if f.until is not None:
        query = query.where(AuditLog.created_at < f.until)
    total = db.session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = db.session.execute(
        query.order_by(AuditLog.id.desc()).offset((page - 1) * limit).limit(limit)
    ).scalars()
    return list(rows), total


def _labels(entries: list[AuditLog]) -> dict[tuple[str, str], str]:
    """Titoli di pagine e nomi di media citati, con una query per tipo (D-124)."""
    from app.models.media import Media
    from app.models.page import Page

    found: dict[tuple[str, str], str] = {}
    sources: tuple[tuple[str, Any, Any], ...] = (
        ("page", Page, Page.title),
        ("media", Media, Media.original_name),
    )
    for entity, model, column in sources:
        ids = {
            int(e.entity_id)
            for e in entries
            if e.entity == entity and e.entity_id and e.entity_id.isdigit()
        }
        if ids:
            rows = db.session.execute(select(model.id, column).where(model.id.in_(ids))).all()
            for item_id, label in rows:
                found[(entity, str(item_id))] = str(label)
    return found


def _emails(entries: list[AuditLog]) -> dict[int, str]:
    from app.models.user import User

    ids = {e.user_id for e in entries if e.user_id is not None}
    if not ids:
        return {}
    rows = db.session.execute(select(User.id, User.email).where(User.id.in_(ids))).all()
    return {user_id: email for user_id, email in rows}


def serialize_many(entries: list[AuditLog]) -> list[dict[str, Any]]:
    labels, emails = _labels(entries), _emails(entries)
    return [
        {
            **serialize(entry),
            "actor_email": emails.get(entry.user_id) if entry.user_id is not None else None,
            "entity_label": labels.get((entry.entity or "", entry.entity_id or "")),
        }
        for entry in entries
    ]


def serialize(entry: AuditLog) -> dict[str, Any]:
    """Per il pannello dell'owner. L'impronta dell'IP resta interna."""
    return {
        "id": entry.id,
        "user_id": entry.user_id,
        "action": entry.action,
        "entity": entry.entity,
        "entity_id": entry.entity_id,
        "diff": entry.diff_json,
        "created_at": entry.created_at.isoformat(),
    }
