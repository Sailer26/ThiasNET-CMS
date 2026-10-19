"""Impostazioni del sito e dell'aspetto (D-14, D-143). Mai "theme" nei nomi: il tema non si
tocca dal pannello, si scelgono solo valori dichiarati in `theme.json > settings`."""

from __future__ import annotations

from typing import Any

from flask import Response

from app.api import ok
from app.api.admin import bp
from app.api.admin.decorators import current, require_permission
from app.api.validation import json_body
from app.services import settings_store
from app.services.permissions import Permission
from app.services.theme import active_theme

EDIT = Permission.SETTINGS_EDIT
MAX_VALUES = 64
BODY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["version", "values"],
    "properties": {
        "version": {"type": "integer", "minimum": 0},
        "values": {"type": "object", "maxProperties": MAX_VALUES},
    },
}


@bp.get("/settings")
@require_permission(EDIT)
def read_settings() -> Response:
    theme = active_theme()
    return ok({scope: settings_store.section(scope, theme) for scope in settings_store.SCOPES})


def _store(scope: str) -> Response:
    body = json_body(BODY_SCHEMA)
    return ok(settings_store.store_settings(current(), scope, body["version"], body["values"]))


@bp.put("/settings/site")
@require_permission(EDIT)
def store_site_settings() -> Response:
    return _store("site")


@bp.put("/settings/appearance")
@require_permission(EDIT)
def store_appearance_settings() -> Response:
    return _store("appearance")
