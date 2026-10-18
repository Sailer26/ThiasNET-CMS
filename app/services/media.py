"""Libreria media: caricamento, modifica, sostituzione ed eliminazione (D-70 … D-85).

Ordine tra file e database:
- caricamento e nuove revisioni: prima i file, poi il commit; se il commit fallisce i file
  appena scritti si cancellano;
- dopo il commit si cancellano i file della revisione precedente (un errore va solo nel log).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from flask import current_app
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import set_committed_value

from app.extensions import db
from app.models.media import ALT_MAX_LENGTH, NAME_MAX_LENGTH, Media, MediaKind
from app.models.user import User
from app.services import audit, media_library, media_refs, media_storage, page_cache
from app.services.errors import ServiceError, not_found, version_conflict
from app.services.media_folders import get_folder
from app.services.media_images import (
    EncodedImage,
    ImageError,
    Variant,
    process,
    variants_from_master,
)
from app.services.media_types import DetectedType, sniff
from app.services.permissions import Permission, require
from app.services.sanitize import clean_line
from app.services.sql import rows_affected
from app.services.theme import active_theme

MB = 1024 * 1024


@dataclass(frozen=True)
class Built:
    files: Mapping[str, bytes]
    variants_json: dict[str, Any]
    width: int | None
    height: int | None
    mime: str
    ext: str

    @property
    def size_bytes(self) -> int:
        return sum(len(data) for data in self.files.values())


def get_media(media_id: int) -> Media:
    media = db.session.get(Media, media_id)
    if media is None:
        raise not_found("File non trovato")
    return media


def _unsupported() -> ServiceError:
    return ServiceError(
        "unsupported_type",
        "Formato non ammesso: carica una foto (JPG, PNG, WebP, GIF) o un PDF",
        415,
    )


def _detect(data: bytes) -> DetectedType:
    if not data:
        raise ServiceError("empty_file", "Il file è vuoto", 422)
    detected = sniff(data)
    if detected is None:
        raise _unsupported()
    return detected


def _original_name(raw: str) -> str:
    """Solo per mostrarlo e per il download dei PDF: mai usato come nome su disco (D-74)."""
    base = PureWindowsPath(PurePosixPath(raw or "").name).name
    return clean_line(base)[:NAME_MAX_LENGTH] or "file"


def _build(detected: DetectedType, data: bytes, rev: int, focal: tuple[int, int]) -> Built:
    if detected.kind == MediaKind.DOCUMENT:
        return Built({f"r{rev}.pdf": data}, {}, None, None, detected.mime, detected.ext)
    max_pixels = int(current_app.config["MEDIA_MAX_PIXELS"])
    try:
        encoded, found = process(
            data,
            detected.format,
            max_pixels=max_pixels,
            image_sizes=active_theme().image_sizes,
            focal=focal,
        )
    except ImageError as exc:
        raise ServiceError("invalid_image", str(exc), 422) from exc
    return _layout(rev, encoded, found)


def _layout(rev: int, encoded: EncodedImage, found: list[Variant]) -> Built:
    master_name = f"r{rev}-master.{encoded.ext}"
    files = {master_name: encoded.data}
    sizes: dict[str, list[dict[str, Any]]] = {}
    for variant in found:
        name = f"r{rev}-{variant.size}-{variant.width}.webp"
        files[name] = variant.data
        sizes.setdefault(variant.size, []).append(
            {"w": variant.width, "h": variant.height, "file": name}
        )
    layout = {
        "master": {"file": master_name, "w": encoded.width, "h": encoded.height},
        "sizes": sizes,
    }
    return Built(files, layout, encoded.width, encoded.height, encoded.mime, encoded.ext)


def _ensure_quota(new_bytes: int, freed_bytes: int = 0) -> None:
    limit = int(current_app.config["MEDIA_QUOTA_MB"]) * MB
    if media_library.used_bytes() - freed_bytes + new_bytes > limit:
        raise ServiceError("storage_full", "Spazio esaurito, contatta Thias", 507)


def _store(key: str, files: Mapping[str, bytes], current: list[str] | None = None) -> None:
    written: list[str] = []
    try:
        for name, data in files.items():
            media_storage.put_replacing_orphan(key, name, data, current or [])
            written.append(name)
    except Exception:
        media_storage.discard(key, written)
        raise


def _commit_or_discard(key: str, files: Mapping[str, bytes]) -> None:
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        media_storage.discard(key, list(files))
        raise


def _by_sha(digest: str) -> Media | None:
    return db.session.execute(select(Media).where(Media.sha256 == digest)).scalar_one_or_none()


def _alt(raw: str) -> str:
    alt = clean_line(raw)
    if len(alt) > ALT_MAX_LENGTH:
        raise ServiceError(
            "invalid_alt", f"Il testo alternativo ha al massimo {ALT_MAX_LENGTH} caratteri", 422
        )
    return alt


def upload(
    actor: User, data: bytes, raw_name: str, *, folder_id: int | None = None, alt: str = ""
) -> tuple[Media, bool]:
    """Restituisce il media e se era già nella libreria (doppione, D-76)."""
    require(actor, Permission.CONTENT_EDIT)
    detected = _detect(data)
    digest = hashlib.sha256(data).hexdigest()
    existing = _by_sha(digest)
    if existing is not None:
        return existing, True
    if folder_id is not None:
        get_folder(folder_id)
    name, clean_alt = _original_name(raw_name), _alt(alt)
    built = _build(detected, data, 1, (50, 50))
    _ensure_quota(built.size_bytes)
    key = media_storage.new_key()
    _store(key, built.files)
    media = Media(
        storage_key=key,
        kind=detected.kind,
        mime=built.mime,
        ext=built.ext,
        original_name=name,
        search_key=media_library.search_key(name, clean_alt),
        size_bytes=built.size_bytes,
        sha256=digest,
        width=built.width,
        height=built.height,
        alt=clean_alt,
        variants_json=built.variants_json,
        folder_id=folder_id,
        created_by=actor.id,
        updated_by=actor.id,
    )
    db.session.add(media)
    try:
        db.session.flush()
    except IntegrityError:  # lo stesso file caricato da due richieste nello stesso istante
        db.session.rollback()
        media_storage.discard(key, list(built.files))
        found = _by_sha(digest)
        if found is None:
            raise
        return found, True
    audit.record(
        "media.uploaded",
        actor_id=actor.id,
        entity="media",
        entity_id=media.id,
        diff={"name": name, "kind": detected.kind, "size": built.size_bytes},
    )
    _commit_or_discard(key, built.files)
    return media, False


def _bump(media: Media, expected: int) -> None:
    if media.version != expected:
        raise version_conflict(media.version, media.updated_by, media.updated_at)
    statement = (
        update(Media)
        .where(Media.id == media.id, Media.version == expected)
        .values(version=expected + 1)
        .execution_options(synchronize_session=False)
    )
    if rows_affected(statement) != 1:
        db.session.rollback()
        fresh = get_media(media.id)
        raise version_conflict(fresh.version, fresh.updated_by, fresh.updated_at)
    set_committed_value(media, "version", expected + 1)


def _new_revision(media: Media, built: Built) -> list[str]:
    """Aggiorna il media alla revisione nuova e restituisce i file di quella vecchia."""
    old = media_library.stored_files(media)
    media.variants_json = built.variants_json
    media.width, media.height, media.mime, media.ext = (
        built.width,
        built.height,
        built.mime,
        built.ext,
    )
    media.size_bytes = built.size_bytes
    return old


def _reprocess(media: Media) -> tuple[Built, list[str]]:
    """Nuove varianti dal master conservato (cambio del punto focale)."""
    master_name = media_library.master_file(media)
    path = media_storage.existing(media.storage_key, master_name or "")
    if path is None:
        raise ServiceError("missing_file", "Il file originale non è più disponibile", 409)
    data = path.read_bytes()
    try:
        found = variants_from_master(
            data,
            media.ext,
            image_sizes=active_theme().image_sizes,
            focal=(media.focal_x, media.focal_y),
        )
    except ImageError as exc:
        raise ServiceError("invalid_image", str(exc), 422) from exc
    # Il master non si ricodifica (niente perdita di qualità): stessi byte, revisione nuova.
    encoded = EncodedImage(data, media.width or 0, media.height or 0, media.ext, media.mime)
    built = _layout(media.file_rev + 1, encoded, found)
    return built, _new_revision(media, built)


def update_media(actor: User, media: Media, version: int, changes: Mapping[str, Any]) -> Media:
    require(actor, Permission.CONTENT_EDIT)
    diff: dict[str, Any] = {}
    if "alt" in changes:
        alt = _alt(changes["alt"])
        if (
            not alt
            and media.alt
            and media.kind == MediaKind.IMAGE
            and media_refs.used_by_online_pages(media.id)
        ):
            raise ServiceError(
                "alt_required",
                "L'immagine è usata in pagine online: il testo alternativo serve",
                422,
            )
        diff["alt"] = [media.alt, alt]
    if "name" in changes:
        diff["name"] = [media.original_name, _original_name(changes["name"])]
    if "folder_id" in changes and changes["folder_id"] is not None:
        get_folder(changes["folder_id"])
    focal = (changes.get("focal_x", media.focal_x), changes.get("focal_y", media.focal_y))
    refocus = media.kind == MediaKind.IMAGE and focal != (media.focal_x, media.focal_y)
    _bump(media, version)
    if "alt" in diff:
        media.alt = diff["alt"][1]
    if "name" in diff:
        media.original_name = diff["name"][1]
    if "folder_id" in changes:
        diff["folder_id"] = [media.folder_id, changes["folder_id"]]
        media.folder_id = changes["folder_id"]
    media.search_key = media_library.search_key(media.original_name, media.alt)
    media.updated_by = actor.id
    old: list[str] = []
    built: Built | None = None
    if refocus:
        diff["focal"] = [[media.focal_x, media.focal_y], list(focal)]
        media.focal_x, media.focal_y = focal
        built, old = _reprocess(media)
        _store(media.storage_key, built.files)
        media.file_rev += 1
    if diff.keys() - {"folder_id"}:
        page_cache.mark_changed()  # alt, nome o ritaglio: le pagine mostrano altro (D-83)
    audit.record("media.updated", actor_id=actor.id, entity="media", entity_id=media.id, diff=diff)
    _commit_or_discard(media.storage_key, built.files if built else {})
    media_storage.discard(media.storage_key, old)
    return media


def replace_file(actor: User, media: Media, version: int, data: bytes, raw_name: str) -> Media:
    """D-85: stesso media e stesso tipo, file nuovo; i PDF tengono lo stesso indirizzo."""
    require(actor, Permission.CONTENT_EDIT)
    detected = _detect(data)
    if detected.kind != media.kind:
        raise ServiceError(
            "kind_mismatch", "Sostituisci un'immagine con un'immagine e un PDF con un PDF", 422
        )
    digest = hashlib.sha256(data).hexdigest()
    other = _by_sha(digest)
    if other is not None and other.id != media.id:
        raise ServiceError("duplicate", "Questo file è già nella libreria con un altro nome", 409)
    built = _build(detected, data, media.file_rev + 1, (media.focal_x, media.focal_y))
    _ensure_quota(built.size_bytes, freed_bytes=media.size_bytes)
    _bump(media, version)
    _store(media.storage_key, built.files)
    old = _new_revision(media, built)
    name = _original_name(raw_name)
    media.file_rev += 1
    media.sha256, media.original_name, media.updated_by = digest, name, actor.id
    media.search_key = media_library.search_key(name, media.alt)
    page_cache.mark_changed()
    audit.record(
        "media.file_replaced",
        actor_id=actor.id,
        entity="media",
        entity_id=media.id,
        diff={"name": name},
    )
    _commit_or_discard(media.storage_key, built.files)
    media_storage.discard(media.storage_key, old)
    return media


def delete_media(actor: User, media: Media, version: int) -> None:
    """D-79: un media usato da una pagina non si elimina; l'errore dice quali pagine."""
    require(actor, Permission.CONTENT_EDIT)
    usages = media_refs.pages_using(media.id)
    if usages:
        raise ServiceError(
            "media_in_use",
            "Il file è usato in alcune pagine: toglilo da lì prima di eliminarlo",
            409,
            details=usages,
        )
    _bump(media, version)
    key, files = media.storage_key, media_library.stored_files(media)
    audit.record(
        "media.deleted",
        actor_id=actor.id,
        entity="media",
        entity_id=media.id,
        diff={"name": media.original_name},
    )
    db.session.delete(media)
    page_cache.mark_changed()
    db.session.commit()
    media_storage.discard(key, files)


# --- Varianti dopo un cambio del tema (D-73) ---------------------------------------------

CORE_SIZES = frozenset({"_panel", "_og"})


def media_missing_variants() -> list[Media]:
    expected = set(active_theme().image_sizes) | CORE_SIZES
    images = db.session.execute(select(Media).where(Media.kind == MediaKind.IMAGE)).scalars()
    return [m for m in images if not expected <= set(media_library.size_files(m))]


def refresh_variants(items: list[Media]) -> tuple[int, int]:
    """Nuova revisione con tutte le varianti del tema attuale; un errore non ferma le altre."""
    done = failed = 0
    for item in items:
        try:
            _bump(item, item.version)  # chi ha il media aperto nel pannello vedrà il cambio
            built, old = _reprocess(item)
            _store(item.storage_key, built.files)
            item.file_rev += 1
            page_cache.mark_changed()
            audit.record(
                "media.variants_refreshed", actor_id=None, entity="media", entity_id=item.id
            )
            _commit_or_discard(item.storage_key, built.files)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("varianti del media %s non create", item.id)
            failed += 1
            continue
        media_storage.discard(item.storage_key, old)
        done += 1
    return done, failed
