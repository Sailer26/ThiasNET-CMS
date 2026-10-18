"""Cartelle della libreria media (D-82): al massimo 3 livelli, nomi unici, niente cicli."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.media import FOLDER_NAME_MAX_LENGTH, Media, MediaFolder
from app.models.user import User
from app.services import audit
from app.services.errors import ServiceError, not_found
from app.services.media_library import normalize
from app.services.permissions import Permission, require
from app.services.sanitize import clean_line

MAX_FOLDER_DEPTH = 3


def get_folder(folder_id: int) -> MediaFolder:
    folder = db.session.get(MediaFolder, folder_id)
    if folder is None:
        raise not_found("Cartella non trovata")
    return folder


def _name(raw: str) -> tuple[str, str]:
    name = clean_line(raw)
    if not name or len(name) > FOLDER_NAME_MAX_LENGTH:
        raise ServiceError(
            "invalid_name",
            f"Il nome della cartella va da 1 a {FOLDER_NAME_MAX_LENGTH} caratteri",
            422,
        )
    return name, normalize(name)[:FOLDER_NAME_MAX_LENGTH]


def _depth(folder: MediaFolder | None) -> int:
    depth = 0
    while folder is not None:
        depth += 1
        folder = db.session.get(MediaFolder, folder.parent_id) if folder.parent_id else None
    return depth


def _children(folder_id: int | None) -> list[MediaFolder]:
    parent = (
        MediaFolder.parent_id.is_(None) if folder_id is None else MediaFolder.parent_id == folder_id
    )
    return list(db.session.execute(select(MediaFolder).where(parent)).scalars())


def _height(folder: MediaFolder) -> int:
    return 1 + max((_height(child) for child in _children(folder.id)), default=0)


def _ensure_free(name_key: str, parent_id: int | None, exclude: int | None = None) -> None:
    for sibling in _children(parent_id):
        if sibling.name_key == name_key and sibling.id != exclude:
            raise ServiceError("folder_exists", "Esiste già una cartella con questo nome", 409)


def _commit() -> None:
    try:
        db.session.commit()
    except IntegrityError as exc:  # due richieste nello stesso istante
        db.session.rollback()
        raise ServiceError("folder_exists", "Esiste già una cartella con questo nome", 409) from exc


def create_folder(actor: User, name: str, parent_id: int | None) -> MediaFolder:
    require(actor, Permission.CONTENT_EDIT)
    clean, key = _name(name)
    parent = get_folder(parent_id) if parent_id is not None else None
    if _depth(parent) + 1 > MAX_FOLDER_DEPTH:
        raise ServiceError(
            "folder_too_deep", f"Al massimo {MAX_FOLDER_DEPTH} livelli di cartelle", 422
        )
    _ensure_free(key, parent_id)
    folder = MediaFolder(name=clean, name_key=key, parent_id=parent_id)
    db.session.add(folder)
    db.session.flush()
    audit.record(
        "media_folder.created", actor_id=actor.id, entity="media_folder", entity_id=folder.id
    )
    _commit()
    return folder


def _is_inside(candidate: MediaFolder | None, folder: MediaFolder) -> bool:
    while candidate is not None:
        if candidate.id == folder.id:
            return True
        candidate = (
            db.session.get(MediaFolder, candidate.parent_id) if candidate.parent_id else None
        )
    return False


def update_folder(actor: User, folder: MediaFolder, changes: Mapping[str, Any]) -> MediaFolder:
    require(actor, Permission.CONTENT_EDIT)
    name, key = _name(changes["name"]) if "name" in changes else (folder.name, folder.name_key)
    parent_id = changes.get("parent_id", folder.parent_id)
    parent = get_folder(parent_id) if parent_id is not None else None
    if _is_inside(parent, folder):
        raise ServiceError("folder_cycle", "Una cartella non può stare dentro se stessa", 422)
    if _depth(parent) + _height(folder) > MAX_FOLDER_DEPTH:
        raise ServiceError(
            "folder_too_deep", f"Al massimo {MAX_FOLDER_DEPTH} livelli di cartelle", 422
        )
    _ensure_free(key, parent_id, exclude=folder.id)
    diff = {"name": [folder.name, name], "parent_id": [folder.parent_id, parent_id]}
    folder.name, folder.name_key, folder.parent_id = name, key, parent_id
    action = "media_folder.moved" if diff["parent_id"][0] != parent_id else "media_folder.renamed"
    audit.record(action, actor_id=actor.id, entity="media_folder", entity_id=folder.id, diff=diff)
    _commit()
    return folder


def delete_folder(actor: User, folder: MediaFolder) -> None:
    require(actor, Permission.CONTENT_EDIT)
    files = db.session.execute(
        select(func.count()).select_from(Media).where(Media.folder_id == folder.id)
    ).scalar_one()
    if files or _children(folder.id):
        raise ServiceError(
            "folder_not_empty", "La cartella non è vuota: sposta prima il contenuto", 409
        )
    audit.record(
        "media_folder.deleted", actor_id=actor.id, entity="media_folder", entity_id=folder.id
    )
    db.session.delete(folder)
    db.session.commit()


def tree() -> list[dict[str, Any]]:
    folders = list(db.session.execute(select(MediaFolder).order_by(MediaFolder.name_key)).scalars())
    children: dict[int, list[dict[str, Any]]] = {f.id: [] for f in folders}
    nodes: dict[int, dict[str, Any]] = {
        f.id: {"id": f.id, "name": f.name, "parent_id": f.parent_id, "children": children[f.id]}
        for f in folders
    }
    roots: list[dict[str, Any]] = []
    for folder in folders:
        siblings = children.get(folder.parent_id, roots) if folder.parent_id is not None else roots
        siblings.append(nodes[folder.id])
    return roots
