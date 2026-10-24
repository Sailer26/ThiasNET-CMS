"""Widget per area (D-140, D-142): li cambia chi può pubblicare e vanno online subito."""

from __future__ import annotations

from typing import Any

from flask import Response

from app.api import ok
from app.api.admin import bp
from app.api.admin.decorators import current, require_permission
from app.api.validation import json_body
from app.services import widgets
from app.services.permissions import Permission
from app.services.theme import active_theme

PUBLISH = Permission.PUBLISH
STORE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["version", "items"],
    "properties": {"version": {"type": "integer", "minimum": 0}, "items": {"type": "array"}},
}


@bp.get("/widgets")
@require_permission(PUBLISH)
def list_widget_areas() -> Response:
    return ok(widgets.all_editable(active_theme()))


@bp.get("/widgets/<area>")
@require_permission(PUBLISH)
def read_widget_area(area: str) -> Response:
    return ok(widgets.editable(area, active_theme()))


@bp.put("/widgets/<area>")
@require_permission(PUBLISH)
def store_widget_area(area: str) -> Response:
    body = json_body(STORE_SCHEMA)
    theme = active_theme()
    return ok(widgets.store_area(current(), area, body["version"], body["items"], theme))
