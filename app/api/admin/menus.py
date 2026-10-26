"""Menu del sito (D-140, D-141): li cambia chi può pubblicare e vanno online subito."""

from __future__ import annotations

from typing import Any

from flask import Response

from app.api import ok
from app.api.admin import bp
from app.api.admin.decorators import current, require_permission
from app.api.admin.locale import panel_locale
from app.api.validation import json_body
from app.services import menus
from app.services.permissions import Permission
from app.services.theme import active_theme

PUBLISH = Permission.PUBLISH
VERSION = {"type": "integer", "minimum": 0}
STORE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["version", "items"],
    "properties": {"version": VERSION, "items": {"type": "array"}},
}
RESET_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["version"],
    "properties": {"version": VERSION},
}


@bp.get("/menus")
@require_permission(PUBLISH)
def list_menus() -> Response:
    return ok(menus.all_editable(active_theme(), panel_locale()))


@bp.get("/menus/<location>")
@require_permission(PUBLISH)
def read_menu(location: str) -> Response:
    return ok(menus.editable(location, active_theme(), panel_locale()))


@bp.put("/menus/<location>")
@require_permission(PUBLISH)
def store_menu(location: str) -> Response:
    body = json_body(STORE_SCHEMA)
    theme, locale = active_theme(), panel_locale()
    return ok(menus.store_menu(current(), location, body["version"], body["items"], theme, locale))


@bp.delete("/menus/<location>")
@require_permission(PUBLISH)
def reset_menu(location: str) -> Response:
    body = json_body(RESET_SCHEMA)
    theme, locale = active_theme(), panel_locale()
    return ok(menus.reset_menu(current(), location, body["version"], theme, locale))
