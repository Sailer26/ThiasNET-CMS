"""Messaggi del modulo contatti (D-126): solo amministratori e owner, mai in cache."""

from __future__ import annotations

from typing import Any

from flask import Response, request

from app.api import ok
from app.api.admin import bp
from app.api.admin.decorators import current, require_permission
from app.api.validation import json_body, page_meta, pagination
from app.services import contact_messages
from app.services.permissions import Permission

VIEW = Permission.MESSAGES_VIEW
QUERY_MAX_LENGTH = 100
READ_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["read"],
    "properties": {"read": {"type": "boolean"}},
}


@bp.get("/messages")
@require_permission(VIEW)
def list_messages() -> Response:
    page_no, limit = pagination()
    items, total = contact_messages.list_messages(
        q=(request.args.get("q") or "").strip()[:QUERY_MAX_LENGTH] or None,
        unread=request.args.get("unread") in {"1", "true"},
        page_no=page_no,
        limit=limit,
    )
    return ok(contact_messages.serialize_list(items), meta=page_meta(page_no, limit, total))


@bp.get("/messages/summary")
@require_permission(VIEW)
def messages_summary() -> Response:
    return ok(contact_messages.summary())


@bp.get("/messages/<int:message_id>")
@require_permission(VIEW)
def get_message(message_id: int) -> Response:
    return ok(contact_messages.serialize_one(contact_messages.get_message(message_id)))


@bp.patch("/messages/<int:message_id>")
@require_permission(VIEW)
def update_message(message_id: int) -> Response:
    body = json_body(READ_SCHEMA)
    message = contact_messages.set_read(contact_messages.get_message(message_id), body["read"])
    return ok(contact_messages.serialize_one(message))


@bp.delete("/messages/<int:message_id>")
@require_permission(VIEW)
def delete_message(message_id: int) -> Response:
    contact_messages.delete_message(current(), contact_messages.get_message(message_id))
    return ok()
