"""Route delle bozze e dei singoli blocchi (D-07, D-39, D-44): usate dall'autosave del pannello."""

from __future__ import annotations

from typing import Any

from flask import Response

from app.api import ok
from app.api.admin import bp
from app.api.admin.decorators import current, require_permission
from app.api.validation import json_body
from app.models.page import NAME_MAX_LENGTH
from app.services import drafts, pages
from app.services.permissions import Permission

EDIT = Permission.CONTENT_EDIT
_VERSION = {"type": "integer", "minimum": 0}
_NAME = {"type": "string", "maxLength": NAME_MAX_LENGTH}
_VARIANT = {"type": ["string", "null"], "maxLength": NAME_MAX_LENGTH}
_UID = {"type": "string", "maxLength": 32}

# Il documento (title, layout, seo, zones) lo valida il servizio contenuti, campo per campo.
DOCUMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["version", "title", "layout", "seo", "zones"],
    "properties": {"version": _VERSION},
}
VERSION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["version"],
    "properties": {"version": _VERSION},
}
ADD_BLOCK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["version", "zone", "type", "data"],
    "properties": {
        "version": _VERSION,
        "zone": _NAME,
        "type": {"type": "string", "maxLength": 32},
        "variant": _VARIANT,
        "data": {"type": "object"},
        "position": {"type": "integer", "minimum": 0},
    },
}
UPDATE_BLOCK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["version"],
    "minProperties": 2,
    "properties": {"version": _VERSION, "variant": _VARIANT, "data": {"type": "object"}},
}
REORDER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["version", "zones"],
    "properties": {
        "version": _VERSION,
        "zones": {
            "type": "object",
            "maxProperties": 32,
            "propertyNames": {"maxLength": 64},
            "additionalProperties": {"type": "array", "maxItems": 200, "items": _UID},
        },
    },
}


def _block_response(result: tuple[int, dict[str, Any]], status: int = 200) -> Response:
    version, block = result
    return ok({"version": version, "block": block}, status=status)


@bp.get("/pages/<int:page_id>/draft")
@require_permission(EDIT)
def get_draft(page_id: int) -> Response:
    return ok(drafts.view(pages.get_page(page_id)))


@bp.put("/pages/<int:page_id>/draft")
@require_permission(EDIT)
def put_draft(page_id: int) -> Response:
    body = json_body(DOCUMENT_SCHEMA)
    document = {k: v for k, v in body.items() if k != "version"}
    version = drafts.store_draft(current(), pages.get_page(page_id), body["version"], document)
    return ok({"version": version})


@bp.delete("/pages/<int:page_id>/draft")
@require_permission(EDIT)
def discard_draft(page_id: int) -> Response:
    body = json_body(VERSION_SCHEMA)
    drafts.discard(current(), pages.get_page(page_id), body["version"])
    return ok({"version": 0})


@bp.post("/pages/<int:page_id>/draft/blocks")
@require_permission(EDIT)
def add_block(page_id: int) -> Response:
    body = json_body(ADD_BLOCK_SCHEMA)
    result = drafts.add_block(
        current(),
        pages.get_page(page_id),
        body["version"],
        zone=body["zone"],
        block_type=body["type"],
        data=body["data"],
        variant=body.get("variant"),
        position=body.get("position"),
    )
    return _block_response(result, 201)


@bp.patch("/pages/<int:page_id>/draft/blocks/<uid>")
@require_permission(EDIT)
def update_block(page_id: int, uid: str) -> Response:
    body = json_body(UPDATE_BLOCK_SCHEMA)
    changes = {k: v for k, v in body.items() if k != "version"}
    page = pages.get_page(page_id)
    return _block_response(drafts.update_block(current(), page, body["version"], uid, changes))


@bp.delete("/pages/<int:page_id>/draft/blocks/<uid>")
@require_permission(EDIT)
def delete_block(page_id: int, uid: str) -> Response:
    body = json_body(VERSION_SCHEMA)
    version = drafts.delete_block(current(), pages.get_page(page_id), body["version"], uid)
    return ok({"version": version})


@bp.post("/pages/<int:page_id>/draft/blocks/reorder")
@require_permission(EDIT)
def reorder_blocks(page_id: int) -> Response:
    body = json_body(REORDER_SCHEMA)
    page = pages.get_page(page_id)
    version = drafts.reorder_blocks(current(), page, body["version"], body["zones"])
    return ok({"version": version})
