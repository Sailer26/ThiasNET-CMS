"""'Chiedi a Thias' (D-134): tutti i ruoli possono chiedere aiuto."""

from __future__ import annotations

from typing import Any

from flask import Response

from app.api import ok
from app.api.admin import bp
from app.api.admin.decorators import current, require_permission
from app.api.validation import json_body
from app.models.support import SCREEN_MAX_LENGTH
from app.services import support
from app.services.permissions import Permission

# Limiti larghi prima della pulizia; il servizio controlla quelli veri.
SUPPORT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["message"],
    "properties": {
        "message": {"type": "string", "maxLength": support.MESSAGE_MAX_LENGTH * 2},
        "page_id": {"type": ["integer", "null"], "minimum": 1},
        "screen": {"type": "string", "maxLength": SCREEN_MAX_LENGTH * 2},
    },
}


@bp.post("/support-requests")
@require_permission(Permission.PROFILE)
def create_support_request() -> Response:
    body = json_body(SUPPORT_SCHEMA)
    request, sent = support.submit(
        current(), body["message"], body.get("page_id"), body.get("screen", "")
    )
    return ok({"id": request.id, "sent": sent}, status=201)
