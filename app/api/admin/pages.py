"""Route delle pagine, della pubblicazione e delle revisioni (D-38…D-48).

Route sottili: validano la forma dell'input e chiamano i servizi, dove stanno logica e permessi.
"""

from __future__ import annotations

from typing import Any

from flask import Response, request

from app.api import ok
from app.api.admin import bp
from app.api.admin.decorators import current, require_permission
from app.api.admin.locale import panel_locale
from app.api.validation import json_body, page_meta, pagination
from app.models.page import (
    LOCALE_LENGTH,
    NAME_MAX_LENGTH,
    PAGE_STATUSES,
    SLUG_MAX_LENGTH,
    Page,
)
from app.services import page_views, pages, prepublish, publishing, revisions, translations
from app.services.errors import ServiceError
from app.services.permissions import Permission
from app.services.theme import active_theme

EDIT, PUBLISH = Permission.CONTENT_EDIT, Permission.PUBLISH
QUERY_MAX_LENGTH = 100
TITLE_INPUT_MAX_LENGTH = 400  # prima della pulizia; il servizio ammette 200 caratteri
_VERSION = {"type": "integer", "minimum": 0}
_PARENT = {"type": ["integer", "null"], "minimum": 1}


def _schema(required: list[str], **properties: Any) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


CREATE_SCHEMA = _schema(
    ["title", "layout"],
    title={"type": "string", "maxLength": TITLE_INPUT_MAX_LENGTH},
    layout={"type": "string", "maxLength": NAME_MAX_LENGTH},
    locale={"type": "string", "maxLength": LOCALE_LENGTH},
    parent_id=_PARENT,
    slug={"type": "string", "maxLength": SLUG_MAX_LENGTH},
)
UPDATE_SCHEMA = {
    **_schema(
        ["version"],
        version=_VERSION,
        slug={"type": "string", "maxLength": SLUG_MAX_LENGTH},
        parent_id=_PARENT,
    ),
    "minProperties": 2,
}
REORDER_SCHEMA = _schema(
    ["parent_id", "locale", "ids"],
    parent_id=_PARENT,
    locale={"type": "string", "maxLength": LOCALE_LENGTH},
    ids={
        "type": "array",
        "maxItems": page_views.TREE_LIMIT,
        "items": {"type": "integer", "minimum": 1},
    },
)
VERSION_SCHEMA = _schema(["version"], version=_VERSION)
DRAFT_VERSION_SCHEMA = _schema(["draft_version"], draft_version=_VERSION)
SCHEDULE_SCHEMA = _schema(
    ["draft_version", "publish_at"],
    draft_version=_VERSION,
    publish_at={"type": "string", "maxLength": 64},
)


def _invalid_query(message: str) -> ServiceError:
    return ServiceError("invalid_query", message, 422)


def _int_arg(name: str) -> int | None:
    raw = request.args.get(name)
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        raise _invalid_query(f"Parametro '{name}' non valido") from None


def _locale_arg(default: str | None) -> str | None:
    locale = request.args.get("locale") or default
    if locale is not None and locale not in active_theme().locales:
        raise _invalid_query("Lingua non attiva in questo sito")
    return locale


def _page_response(page: Page, status: int = 200) -> Response:
    return ok(page_views.serialize_one(page), status=status)


# --- Pagine --------------------------------------------------------------------


@bp.get("/pages")
@require_permission(EDIT)
def list_pages() -> Response:
    page_no, limit = pagination()
    status = request.args.get("status") or None
    if status is not None and status not in PAGE_STATUSES:
        raise _invalid_query("Stato non valido")
    q = (request.args.get("q") or "").strip()[:QUERY_MAX_LENGTH] or None
    items, total = page_views.list_pages(
        locale=_locale_arg(None),
        parent_id=_int_arg("parent_id"),
        status=status,
        q=q,
        page_no=page_no,
        limit=limit,
    )
    return ok(page_views.serialize_many(items), meta=page_meta(page_no, limit, total))


@bp.get("/pages/tree")
@require_permission(EDIT)
def page_tree() -> Response:
    nodes, truncated = page_views.tree(panel_locale())
    return ok(nodes, meta={"truncated": truncated})


@bp.get("/pages/trash")
@require_permission(EDIT)
def list_trash() -> Response:
    page_no, limit = pagination()
    items, total = page_views.list_trash(page_no, limit)
    return ok(page_views.serialize_many(items), meta=page_meta(page_no, limit, total))


@bp.post("/pages")
@require_permission(EDIT)
def create_page() -> Response:
    body = json_body(CREATE_SCHEMA)
    page = pages.create_page(
        current(),
        title=body["title"],
        layout=body["layout"],
        locale=body.get("locale"),
        parent_id=body.get("parent_id"),
        slug=body.get("slug"),
    )
    return _page_response(page, 201)


@bp.post("/pages/reorder")
@require_permission(EDIT)
def reorder_pages() -> Response:
    body = json_body(REORDER_SCHEMA)
    locale = body["locale"]
    if locale not in active_theme().locales:
        raise _invalid_query("Lingua non attiva in questo sito")
    pages.reorder(current(), parent_id=body["parent_id"], locale=locale, ids=body["ids"])
    return ok({"ids": body["ids"]})


@bp.get("/pages/<int:page_id>")
@require_permission(EDIT)
def get_page(page_id: int) -> Response:
    return _page_response(pages.get_page(page_id))


@bp.patch("/pages/<int:page_id>")
@require_permission(EDIT)
def update_page(page_id: int) -> Response:
    body = json_body(UPDATE_SCHEMA)
    changes = {k: v for k, v in body.items() if k != "version"}
    page = pages.update_page(
        current(), pages.get_page(page_id), version=body["version"], changes=changes
    )
    return _page_response(page)


@bp.delete("/pages/<int:page_id>")
@require_permission(EDIT)
def trash_page(page_id: int) -> Response:
    body = json_body(VERSION_SCHEMA)
    return _page_response(pages.trash(current(), pages.get_page(page_id), body["version"]))


@bp.post("/pages/<int:page_id>/restore")
@require_permission(EDIT)
def restore_page(page_id: int) -> Response:
    body = json_body(VERSION_SCHEMA)
    page = pages.restore(current(), pages.get_trashed(page_id), body["version"])
    return _page_response(page)


# --- Pubblicazione ----------------------------------------------------------------


@bp.get("/pages/<int:page_id>/checks")
@require_permission(PUBLISH)
def page_checks(page_id: int) -> Response:
    """Controllo prima di pubblicare (D-135): non scrive nulla."""
    return ok(prepublish.report(pages.get_page(page_id)))


@bp.post("/pages/<int:page_id>/publish")
@require_permission(PUBLISH)
def publish_page(page_id: int) -> Response:
    body = json_body(DRAFT_VERSION_SCHEMA)
    page = publishing.publish(current(), pages.get_page(page_id), body["draft_version"])
    return _page_response(page)


@bp.post("/pages/<int:page_id>/schedule")
@require_permission(PUBLISH)
def schedule_page(page_id: int) -> Response:
    body = json_body(SCHEDULE_SCHEMA)
    page = publishing.schedule(
        current(), pages.get_page(page_id), body["draft_version"], body["publish_at"]
    )
    return _page_response(page)


@bp.delete("/pages/<int:page_id>/schedule")
@require_permission(PUBLISH)
def unschedule_page(page_id: int) -> Response:
    body = json_body(VERSION_SCHEMA)
    page = publishing.unschedule(current(), pages.get_page(page_id), body["version"])
    return _page_response(page)


@bp.post("/pages/<int:page_id>/unpublish")
@require_permission(PUBLISH)
def unpublish_page(page_id: int) -> Response:
    body = json_body(VERSION_SCHEMA)
    page = publishing.unpublish(current(), pages.get_page(page_id), body["version"])
    return _page_response(page)


# --- Revisioni -------------------------------------------------------------------


@bp.get("/pages/<int:page_id>/revisions")
@require_permission(EDIT)
def list_revisions(page_id: int) -> Response:
    page_no, limit = pagination()
    items, total = revisions.list_revisions(pages.get_page(page_id), page_no, limit)
    return ok([revisions.serialize(r) for r in items], meta=page_meta(page_no, limit, total))


@bp.get("/pages/<int:page_id>/revisions/<int:revision_id>")
@require_permission(EDIT)
def get_revision(page_id: int, revision_id: int) -> Response:
    revision = revisions.get_revision(pages.get_page(page_id), revision_id)
    return ok(revisions.serialize(revision, with_snapshot=True))


@bp.post("/pages/<int:page_id>/revisions/<int:revision_id>/restore")
@require_permission(EDIT)
def restore_revision(page_id: int, revision_id: int) -> Response:
    body = json_body(DRAFT_VERSION_SCHEMA)
    version = revisions.restore(
        current(), pages.get_page(page_id), revision_id, body["draft_version"]
    )
    return ok({"version": version})


# --- Traduzioni (D-151) ------------------------------------------------------------------------

TRANSLATE_SCHEMA = _schema(["locale"], locale={"type": "string", "maxLength": 5})


@bp.get("/pages/<int:page_id>/translations")
@require_permission(EDIT)
def list_page_translations(page_id: int) -> Response:
    return ok(translations.page_translations(pages.get_page(page_id)))


@bp.post("/pages/<int:page_id>/translations")
@require_permission(EDIT)
def translate_page(page_id: int) -> Response:
    body = json_body(TRANSLATE_SCHEMA)
    created = translations.translate_page(current(), pages.get_page(page_id), body["locale"])
    return _page_response(created, 201)
