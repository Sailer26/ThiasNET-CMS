"""Route delle raccolte e delle loro voci (Fase 7a, D-147 … D-149).

Le route dichiarano `content.edit`; pubblicare, programmare, ritirare e toccare voci online
chiede anche `content.publish`, e lo controllano i servizi (D-48).
"""

from __future__ import annotations

import math
from typing import Any

from flask import Response, request

from app.api import ok
from app.api.admin import bp
from app.api.admin.decorators import current, require_permission
from app.api.validation import json_body, page_meta, pagination
from app.models.page import SLUG_MAX_LENGTH, TITLE_MAX_LENGTH
from app.services import collections, entries, entry_publishing
from app.services.permissions import Permission
from app.services.theme import active_theme

EDIT = Permission.CONTENT_EDIT
_VERSION = {"type": "integer", "minimum": 0}


def _schema(required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


CREATE_SCHEMA = _schema(
    ["title"],
    {
        "title": {"type": "string", "maxLength": TITLE_MAX_LENGTH * 2},
        "locale": {"type": "string", "maxLength": 5},
    },
)
SLUG_SCHEMA = _schema(
    ["version", "slug"],
    {"version": _VERSION, "slug": {"type": "string", "maxLength": SLUG_MAX_LENGTH}},
)
VERSION_SCHEMA = _schema(["version"], {"version": _VERSION})
PUBLISH_SCHEMA = _schema(["draft_version"], {"draft_version": _VERSION})
SCHEDULE_SCHEMA = _schema(
    ["draft_version", "publish_at"],
    {"draft_version": _VERSION, "publish_at": {"type": "string", "maxLength": 40}},
)
# Il documento (title, fields, seo) lo valida il servizio delle raccolte, campo per campo.
DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["version", "title", "fields", "seo"],
    "properties": {"version": _VERSION},
}


def _entry(entry_id: int) -> dict[str, Any]:
    return entries.serialize(entries.get_entry(entry_id), active_theme())


@bp.get("/collections")
@require_permission(EDIT)
def list_collections() -> Response:
    theme = active_theme()
    found = []
    for key, spec in theme.collections.items():
        listing = entries.listing_page(theme, key, theme.locales[0], online=False)
        found.append(
            {
                "key": key,
                "label": spec.label,
                "per_page": spec.per_page,
                "schema": collections.public_schema(theme, key),
                "listing": None
                if listing is None
                else {"page_id": listing.id, "path": listing.path},
            }
        )
    return ok(found)


@bp.get("/collections/<key>/entries")
@require_permission(EDIT)
def list_entries(key: str) -> Response:
    page, limit = pagination()
    trash = request.args.get("trash") in {"1", "true"}
    rows, total = entries.panel_list(active_theme(), key, page=page, per_page=limit, trash=trash)
    meta = page_meta(page, limit, total) | {"pages": max(1, math.ceil(total / limit))}
    return ok(rows, meta=meta)


@bp.post("/collections/<key>/entries")
@require_permission(EDIT)
def create_entry(key: str) -> Response:
    body = json_body(CREATE_SCHEMA)
    entry = entries.create(current(), key, title=body["title"], locale=body.get("locale"))
    return ok(entries.serialize(entry, active_theme(), has_draft=True), status=201)


@bp.get("/entries/<int:entry_id>")
@require_permission(EDIT)
def read_entry(entry_id: int) -> Response:
    return ok(_entry(entry_id))


@bp.patch("/entries/<int:entry_id>")
@require_permission(EDIT)
def change_entry_slug(entry_id: int) -> Response:
    body = json_body(SLUG_SCHEMA)
    entry = entries.get_entry(entry_id)
    entries.change_slug(current(), entry, body["version"], body["slug"])
    return ok(_entry(entry_id))


@bp.delete("/entries/<int:entry_id>")
@require_permission(EDIT)
def trash_entry(entry_id: int) -> Response:
    body = json_body(VERSION_SCHEMA)
    entry = entries.trash(current(), entries.get_entry(entry_id), body["version"])
    return ok(entries.serialize(entry, active_theme()))


@bp.post("/entries/<int:entry_id>/restore")
@require_permission(EDIT)
def restore_entry(entry_id: int) -> Response:
    body = json_body(VERSION_SCHEMA)
    entries.restore(current(), entries.get_trashed(entry_id), body["version"])
    return ok(_entry(entry_id))


@bp.get("/entries/<int:entry_id>/draft")
@require_permission(EDIT)
def read_entry_draft(entry_id: int) -> Response:
    return ok(entries.draft_view(entries.get_entry(entry_id)))


@bp.put("/entries/<int:entry_id>/draft")
@require_permission(EDIT)
def store_entry_draft(entry_id: int) -> Response:
    body = json_body(DRAFT_SCHEMA)
    document = {key: body[key] for key in ("title", "fields", "seo")}
    entry = entries.get_entry(entry_id)
    version = entries.store_draft(current(), entry, body["version"], document)
    return ok({"version": version})


@bp.delete("/entries/<int:entry_id>/draft")
@require_permission(EDIT)
def discard_entry_draft(entry_id: int) -> Response:
    body = json_body(VERSION_SCHEMA)
    entries.discard_draft(current(), entries.get_entry(entry_id), body["version"])
    return ok(entries.draft_view(entries.get_entry(entry_id)))


@bp.post("/entries/<int:entry_id>/publish")
@require_permission(EDIT)
def publish_entry(entry_id: int) -> Response:
    body = json_body(PUBLISH_SCHEMA)
    entry_publishing.publish(current(), entries.get_entry(entry_id), body["draft_version"])
    return ok(_entry(entry_id))


@bp.post("/entries/<int:entry_id>/schedule")
@require_permission(EDIT)
def schedule_entry(entry_id: int) -> Response:
    body = json_body(SCHEDULE_SCHEMA)
    entry = entries.get_entry(entry_id)
    entry_publishing.schedule(current(), entry, body["draft_version"], body["publish_at"])
    return ok(_entry(entry_id))


@bp.post("/entries/<int:entry_id>/unschedule")
@require_permission(EDIT)
def unschedule_entry(entry_id: int) -> Response:
    body = json_body(VERSION_SCHEMA)
    entry_publishing.unschedule(current(), entries.get_entry(entry_id), body["version"])
    return ok(_entry(entry_id))


@bp.post("/entries/<int:entry_id>/unpublish")
@require_permission(EDIT)
def unpublish_entry(entry_id: int) -> Response:
    body = json_body(VERSION_SCHEMA)
    entry_publishing.unpublish(current(), entries.get_entry(entry_id), body["version"])
    return ok(_entry(entry_id))


@bp.get("/entries/<int:entry_id>/revisions")
@require_permission(EDIT)
def entry_revisions(entry_id: int) -> Response:
    return ok(entries.revisions(entries.get_entry(entry_id)))
