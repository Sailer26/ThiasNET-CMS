"""Libreria media: elenco con ricerca e filtri, indirizzi pubblici, serializzazione (D-75, D-82)."""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from types import MappingProxyType
from typing import Any

from sqlalchemy import func, select

from app.extensions import db
from app.models.media import Media, MediaKind
from app.services.render_context import MediaView, VariantView

SEARCH_KEY_LENGTH = 500
DOCUMENT_FILE = "file.pdf"  # indirizzo stabile dei PDF (D-75, D-85)
PANEL = "_panel"


def normalize(text: str) -> str:
    """Minuscole e senza accenti: "Città" e "CITTA" si trovano allo stesso modo (D-82)."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(plain.split())


def search_key(name: str, alt: str) -> str:
    return normalize(f"{name} {alt}")[:SEARCH_KEY_LENGTH]


def file_url(media: Media, name: str) -> str:
    return f"/media/{media.storage_key}/{name}"


def master_file(media: Media) -> str | None:
    master = (media.variants_json or {}).get("master")
    return master.get("file") if isinstance(master, dict) else None


def public_url(media: Media) -> str:
    if media.kind == MediaKind.DOCUMENT:
        return file_url(media, DOCUMENT_FILE)
    return file_url(media, master_file(media) or "")


def size_files(media: Media) -> dict[str, list[dict[str, Any]]]:
    sizes = (media.variants_json or {}).get("sizes")
    return sizes if isinstance(sizes, dict) else {}


def stored_files(media: Media) -> list[str]:
    """Tutti i file della revisione corrente (master e varianti, oppure il PDF)."""
    if media.kind == MediaKind.DOCUMENT:
        return [f"r{media.file_rev}.pdf"]
    names = [entry["file"] for entries in size_files(media).values() for entry in entries]
    master = master_file(media)
    return [master, *names] if master else names


def thumbnail_url(media: Media) -> str | None:
    panel = size_files(media).get(PANEL)
    if panel:
        return file_url(media, panel[0]["file"])
    return public_url(media) if media.kind == MediaKind.IMAGE else None


def serialize(media: Media, *, used_by: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": media.id,
        "key": media.storage_key,
        "kind": media.kind,
        "name": media.original_name,
        "ext": media.ext,
        "mime": media.mime,
        "size_bytes": media.size_bytes,
        "width": media.width,
        "height": media.height,
        "alt": media.alt,
        "focal_x": media.focal_x,
        "focal_y": media.focal_y,
        "folder_id": media.folder_id,
        "version": media.version,
        "file_rev": media.file_rev,
        "url": public_url(media),
        "thumbnail_url": thumbnail_url(media),
        "sizes": {
            size: [{"w": e["w"], "h": e["h"], "url": file_url(media, e["file"])} for e in entries]
            for size, entries in size_files(media).items()
        },
        "created_at": media.created_at.isoformat(),
        "updated_at": media.updated_at.isoformat(),
    }
    if used_by is not None:
        data["used_by"] = used_by
    return data


def list_media(
    *,
    q: str | None,
    folder_id: int | None,
    kind: str | None,
    missing_alt: bool,
    page_no: int,
    limit: int,
) -> tuple[list[Media], int]:
    query = select(Media)
    if q:
        query = query.where(Media.search_key.contains(normalize(q), autoescape=True))
    if folder_id is not None:
        query = query.where(Media.folder_id == folder_id)
    if kind:
        query = query.where(Media.kind == kind)
    if missing_alt:
        query = query.where(Media.kind == MediaKind.IMAGE, func.trim(Media.alt) == "")
    total = db.session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = db.session.execute(
        query.order_by(Media.created_at.desc(), Media.id.desc())
        .offset((page_no - 1) * limit)
        .limit(limit)
    )
    return list(rows.scalars()), total


def by_ids(ids: Sequence[int]) -> list[Media]:
    """I media con questi id, nell'ordine chiesto; quelli che non esistono si omettono."""
    found = {m.id: m for m in db.session.execute(select(Media).where(Media.id.in_(ids))).scalars()}
    return [found[i] for i in ids if i in found]


def used_bytes() -> int:
    total = db.session.execute(select(func.coalesce(func.sum(Media.size_bytes), 0))).scalar_one()
    return int(total)


def to_view(media: Media) -> MediaView:
    sizes = {
        size: tuple(
            VariantView(e["w"], e["h"], file_url(media, e["file"]))
            for e in sorted(entries, key=lambda e: e["w"])
        )
        for size, entries in size_files(media).items()
    }
    return MediaView(
        id=media.id,
        kind=media.kind,
        alt=media.alt,
        width=media.width,
        height=media.height,
        url=public_url(media),
        name=media.original_name,
        ext=media.ext,
        size_bytes=media.size_bytes,
        focal_x=media.focal_x,
        focal_y=media.focal_y,
        sizes=MappingProxyType(sizes),
    )
