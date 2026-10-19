"""Lettura del registro attività: solo owner."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from flask import Response, request

from app.api import ok
from app.api.admin import bp
from app.api.admin.decorators import require_permission
from app.api.validation import page_meta, pagination
from app.services import audit
from app.services.errors import ServiceError
from app.services.permissions import Permission

ENTITY_ID_MAX_LENGTH = 64
USER_ID_MAX_DIGITS = 9
DATE_LENGTH = len("2026-10-19")


def _invalid(message: str) -> ServiceError:
    return ServiceError("invalid_query", message, 422)


def _bound(name: str, *, end: bool) -> datetime | None:
    """Limite di tempo (D-124): una data AAAA-MM-GG (giorno intero in UTC, "al" compreso)
    oppure un istante ISO con il fuso, come la mezzanotte di Zurigo che manda il pannello
    (il server non ha i fusi su Windows); per "al" l'istante è escluso."""
    raw = request.args.get(name)
    if not raw:
        return None
    try:
        if len(raw) == DATE_LENGTH:
            start = datetime.combine(date.fromisoformat(raw), time.min, UTC)
            return start + timedelta(days=1) if end else start
        moment = datetime.fromisoformat(raw)
    except (ValueError, OverflowError):
        raise _invalid("Data non valida: usa AAAA-MM-GG") from None
    if moment.tzinfo is None:
        raise _invalid("Data non valida: manca il fuso orario")
    return moment.astimezone(UTC)


def _filters() -> audit.AuditFilter:
    """Filtri del registro (D-124): ogni valore controllato, le categorie sono fisse."""
    raw_user = request.args.get("user_id")
    valid_user = raw_user is None or (
        raw_user.isascii() and raw_user.isdigit() and len(raw_user) <= USER_ID_MAX_DIGITS
    )
    if not valid_user:
        raise _invalid("Persona non valida")
    category = request.args.get("category") or None
    if category is not None and category not in audit.CATEGORIES:
        raise _invalid("Tipo non valido")
    entity = request.args.get("entity") or None
    entity_id = request.args.get("entity_id") or None
    if (entity is None) != (entity_id is None) or (
        entity is not None and entity not in audit.ENTITIES
    ):
        raise _invalid("Oggetto non valido")
    if entity_id is not None and len(entity_id) > ENTITY_ID_MAX_LENGTH:
        raise _invalid("Oggetto non valido")
    return audit.AuditFilter(
        user_id=int(raw_user) if raw_user else None,
        category=category,
        entity=entity,
        entity_id=entity_id,
        since=_bound("since", end=False),
        until=_bound("until", end=True),
    )


@bp.get("/audit")
@require_permission(Permission.AUDIT_VIEW)
def list_audit() -> Response:
    page, limit = pagination()
    entries, total = audit.list_entries(page, limit, _filters())
    return ok(audit.serialize_many(entries), meta=page_meta(page, limit, total))
