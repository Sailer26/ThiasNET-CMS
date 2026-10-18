"""Dove sono usati i media (D-78, D-79).

- `document_refs`: i media di un documento di pagina (blocchi + `seo.og_image_media_id`);
- `check_document`: alla pubblicazione, ogni media esiste, è del tipo giusto e, se immagine,
  ha il testo alternativo. La bozza e l'anteprima non lo chiamano mai (D-46);
- `pages_using`: le pagine non cestinate che usano un media (pubblicata, bozza, programmata).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Any

from sqlalchemy import select

from app.extensions import db
from app.models.media import Media, MediaKind
from app.models.page import Block, Page, PageDraft, PageRevision, PageStatus, RevisionKind
from app.services.blocks import FieldError, MediaRef, get_registry
from app.services.page_paths import live

OG_PATH = "seo/og_image_media_id"
MAX_USAGES = 50


def document_refs(document: Any) -> list[MediaRef]:
    if not isinstance(document, Mapping):
        return []
    registry = get_registry()
    refs: list[MediaRef] = []
    zones = document.get("zones")
    if isinstance(zones, Mapping):
        for zone, blocks in zones.items():
            if not isinstance(blocks, Sequence) or isinstance(blocks, str):
                continue
            for index, block in enumerate(blocks):
                if isinstance(block, Mapping) and isinstance(block.get("type"), str):
                    prefix = f"zones/{zone}/{index}/data"
                    refs += registry.media_refs(block["type"], block.get("data"), prefix)
    seo = document.get("seo")
    og = seo.get("og_image_media_id") if isinstance(seo, Mapping) else None
    if isinstance(og, int) and not isinstance(og, bool):
        refs.append(MediaRef(og, MediaKind.IMAGE, OG_PATH))
    return refs


def load(ids: Iterable[int]) -> dict[int, Media]:
    wanted = sorted(set(ids))
    if not wanted:
        return {}
    return {
        m.id: m for m in db.session.execute(select(Media).where(Media.id.in_(wanted))).scalars()
    }


def check_document(document: Any) -> list[FieldError]:
    refs = document_refs(document)
    found = load(ref.media_id for ref in refs)
    errors: list[FieldError] = []
    for ref in refs:
        media = found.get(ref.media_id)
        if media is None:
            errors.append(
                FieldError(ref.path, "media_missing", "Il file non c'è più nella libreria")
            )
        elif ref.kind == MediaKind.IMAGE and media.kind != MediaKind.IMAGE:
            errors.append(FieldError(ref.path, "media_not_image", "Qui serve un'immagine"))
        elif ref.kind == "file" and media.kind != MediaKind.DOCUMENT:
            errors.append(FieldError(ref.path, "media_not_file", "Qui serve un documento PDF"))
        elif media.kind == MediaKind.IMAGE and not media.alt.strip():
            errors.append(
                FieldError(ref.path, "alt_missing", "Aggiungi il testo alternativo all'immagine")
            )
    return errors


def _uses(document: Any, media_id: int) -> bool:
    return any(ref.media_id == media_id for ref in document_refs(document))


def _published(media_id: int) -> Iterator[tuple[Page, str]]:
    registry = get_registry()
    # Anche le pagine ritirate o tornate dal cestino: i blocchi si ripubblicano così come sono.
    rows = db.session.execute(
        select(Block, Page).join(Page, Page.id == Block.page_id).where(live())
    )
    for block, page in rows:
        if media_id in registry.media_ids(block.type, block.data_json):
            yield page, _where(page)
    for page in db.session.execute(select(Page).where(live())).scalars():
        if (page.seo_json or {}).get("og_image_media_id") == media_id:
            yield page, _where(page)


def _where(page: Page) -> str:
    return "published" if page.status == PageStatus.PUBLISHED else "unpublished"


def _drafts(media_id: int) -> Iterator[tuple[Page, str]]:
    rows = db.session.execute(
        select(PageDraft, Page).join(Page, Page.id == PageDraft.page_id).where(live())
    )
    for draft, page in rows:
        if _uses(draft.data_json, media_id):
            yield page, "draft"


def _scheduled(media_id: int) -> Iterator[tuple[Page, str]]:
    rows = db.session.execute(
        select(PageRevision, Page)
        .join(Page, Page.id == PageRevision.page_id)
        .where(live(), PageRevision.kind == RevisionKind.SCHEDULED)
    )
    for revision, page in rows:
        if _uses(revision.snapshot_json, media_id):
            yield page, "scheduled"


# Fonti di "in uso": dalla Fase 6 si aggiungono widget e impostazioni, dalla 7 le collezioni.
SOURCES = (_published, _drafts, _scheduled)


def pages_using(media_id: int) -> list[dict[str, Any]]:
    seen: set[tuple[int, str]] = set()
    usages: list[dict[str, Any]] = []
    for source in SOURCES:
        for page, where in source(media_id):
            if (page.id, where) in seen:
                continue
            seen.add((page.id, where))
            usages.append(
                {"page_id": page.id, "title": page.title, "path": page.path, "where": where}
            )
            if len(usages) >= MAX_USAGES:
                return usages
    return usages


def used_by_online_pages(media_id: int) -> bool:
    """Usato da una pagina online o programmata (per non togliere l'alt, D-77): si guardano
    solo queste due fonti e ci si ferma al primo caso, senza il tetto di MAX_USAGES."""
    online = (where for _page, where in _published(media_id) if where == "published")
    return next(online, None) is not None or next(_scheduled(media_id), None) is not None
