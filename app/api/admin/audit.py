"""Lettura del registro attività: solo owner."""

from __future__ import annotations

from flask import Response

from app.api import ok
from app.api.admin import bp
from app.api.admin.decorators import require_permission
from app.api.validation import page_meta, pagination
from app.services import audit
from app.services.permissions import Permission


@bp.get("/audit")
@require_permission(Permission.AUDIT_VIEW)
def list_audit() -> Response:
    page, limit = pagination()
    entries, total = audit.list_entries(page, limit)
    return ok([audit.serialize(e) for e in entries], meta=page_meta(page, limit, total))
