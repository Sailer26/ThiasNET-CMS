"""Route della libreria media e delle cartelle (D-70 … D-85). Logica in app/services."""

from __future__ import annotations

import re
from typing import Any

from flask import Response, request

from app.api import ok
from app.api.admin import bp
from app.api.admin.decorators import current, require_permission
from app.api.validation import json_body, page_meta, pagination
from app.models.media import MediaKind
from app.services import media, media_folders, media_library, media_refs
from app.services.errors import ServiceError
from app.services.permissions import Permission

EDIT = Permission.CONTENT_EDIT
_VERSION = {"type": "integer", "minimum": 0}
_FOCAL = {"type": "integer", "minimum": 0, "maximum": 100}
_FOLDER = {"type": ["integer", "null"], "minimum": 1}
UPDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["version"],
    "minProperties": 2,
    "properties": {
        "version": _VERSION,
        "name": {"type": "string", "maxLength": 400},
        "alt": {"type": "string", "maxLength": 1000},
        "focal_x": _FOCAL,
        "focal_y": _FOCAL,
        "folder_id": _FOLDER,
    },
}
VERSION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["version"],
    "properties": {"version": _VERSION},
}
FOLDER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name"],
    "properties": {"name": {"type": "string", "maxLength": 200}, "parent_id": _FOLDER},
}
FOLDER_UPDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "minProperties": 1,
    "properties": {"name": {"type": "string", "maxLength": 200}, "parent_id": _FOLDER},
}


def _invalid(message: str) -> ServiceError:
    return ServiceError("invalid_body", message, 422)


def _uploaded_file() -> tuple[bytes, str]:
    """Un solo file nel campo `file` (il limite di dimensione lo applica Flask: 413)."""
    files = request.files.getlist("file")
    if len(files) != 1 or not files[0].filename:
        raise _invalid("Scegli un file da caricare")
    return files[0].read(), files[0].filename


def _form_int(name: str) -> int | None:
    raw = (request.form.get(name) or "").strip()
    if not raw:
        return None
    if not raw.isdigit():
        raise _invalid(f"Valore non valido per '{name}'")
    return int(raw)


MAX_IDS = 100
ID_PART = r"[1-9][0-9]{0,8}"  # sotto 2^31: niente errori con colonne integer di PostgreSQL
IDS_RE = re.compile(rf"{ID_PART}(?:,{ID_PART}){{0,{MAX_IDS - 1}}}")


def _ids(raw: str) -> list[int]:
    """`?ids=3,1,2`: i media già scelti in una pagina, letti con una richiesta sola (D-111)."""
    if not IDS_RE.fullmatch(raw):
        raise _invalid(f"Elenco di id non valido (al massimo {MAX_IDS}, separati da virgole)")
    return list(dict.fromkeys(int(part) for part in raw.split(",")))


@bp.get("/media")
@require_permission(EDIT)
def list_media() -> Response:
    if "ids" in request.args:
        wanted = _ids(request.args["ids"])
        return ok([media_library.serialize(m) for m in media_library.by_ids(wanted)])
    page_no, limit = pagination()
    kind = request.args.get("kind") or None
    if kind is not None and kind not in set(MediaKind):
        raise _invalid("Tipo non valido")
    folder = request.args.get("folder_id") or None
    if folder is not None and not folder.isdigit():
        raise _invalid("Cartella non valida")
    items, total = media_library.list_media(
        q=(request.args.get("q") or "").strip()[:100] or None,
        folder_id=int(folder) if folder else None,
        kind=kind,
        missing_alt=request.args.get("missing_alt") in {"1", "true"},
        page_no=page_no,
        limit=limit,
    )
    return ok([media_library.serialize(m) for m in items], meta=page_meta(page_no, limit, total))


@bp.post("/media")
@require_permission(EDIT)
def upload_media() -> Response:
    data, name = _uploaded_file()
    item, duplicate = media.upload(
        current(), data, name, folder_id=_form_int("folder_id"), alt=request.form.get("alt", "")
    )
    if duplicate:
        return ok(media_library.serialize(item), meta={"duplicate": True})
    return ok(media_library.serialize(item), status=201)


@bp.get("/media/<int:media_id>")
@require_permission(EDIT)
def get_media(media_id: int) -> Response:
    item = media.get_media(media_id)
    return ok(media_library.serialize(item, used_by=media_refs.pages_using(item.id)))


@bp.patch("/media/<int:media_id>")
@require_permission(EDIT)
def update_media(media_id: int) -> Response:
    body = json_body(UPDATE_SCHEMA)
    changes = {k: v for k, v in body.items() if k != "version"}
    item = media.update_media(current(), media.get_media(media_id), body["version"], changes)
    return ok(media_library.serialize(item))


@bp.post("/media/<int:media_id>/file")
@require_permission(EDIT)
def replace_media_file(media_id: int) -> Response:
    data, name = _uploaded_file()
    version = _form_int("version")
    if version is None:
        raise _invalid("Manca la versione")
    item = media.replace_file(current(), media.get_media(media_id), version, data, name)
    return ok(media_library.serialize(item))


@bp.delete("/media/<int:media_id>")
@require_permission(EDIT)
def delete_media(media_id: int) -> Response:
    body = json_body(VERSION_SCHEMA)
    media.delete_media(current(), media.get_media(media_id), body["version"])
    return ok()


# --- Cartelle -----------------------------------------------------------------------


@bp.get("/media/folders")
@require_permission(EDIT)
def list_media_folders() -> Response:
    return ok(media_folders.tree())


@bp.post("/media/folders")
@require_permission(EDIT)
def create_media_folder() -> Response:
    body = json_body(FOLDER_SCHEMA)
    folder = media_folders.create_folder(current(), body["name"], body.get("parent_id"))
    return ok({"id": folder.id, "name": folder.name, "parent_id": folder.parent_id}, status=201)


@bp.patch("/media/folders/<int:folder_id>")
@require_permission(EDIT)
def update_media_folder(folder_id: int) -> Response:
    body = json_body(FOLDER_UPDATE_SCHEMA)
    folder = media_folders.update_folder(current(), media_folders.get_folder(folder_id), body)
    return ok({"id": folder.id, "name": folder.name, "parent_id": folder.parent_id})


@bp.delete("/media/folders/<int:folder_id>")
@require_permission(EDIT)
def delete_media_folder(folder_id: int) -> Response:
    media_folders.delete_folder(current(), media_folders.get_folder(folder_id))
    return ok()
