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


def _invalid(message: str) -> ServiceError:
    return ServiceError("invalid_query", message, 422)


def _day(name: str) -> date | None:
    raw = request.args.get(name)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise _invalid("Data non valida: usa AAAA-MM-GG") from None


def _filters() -> audit.AuditFilter:
    """Filtri del registro (D-124): ogni valore controllato, le categorie sono fisse."""
    raw_user = request.args.get("user_id")
    if raw_user is not None and not raw_user.isdigit():
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
    since, until = _day("since"), _day("until")
    return audit.AuditFilter(
        user_id=int(raw_user) if raw_user else None,
        category=category,
        entity=entity,
        entity_id=entity_id,
        since=datetime.combine(since, time.min, UTC) if since else None,
        # "al" comprende tutto il giorno indicato
        until=datetime.combine(until, time.min, UTC) + timedelta(days=1) if until else None,
    )


@bp.get("/audit")
@require_permission(Permission.AUDIT_VIEW)
def list_audit() -> Response:
    page, limit = pagination()
    entries, total = audit.list_entries(page, limit, _filters())
    return ok(audit.serialize_many(entries), meta=page_meta(page, limit, total))
