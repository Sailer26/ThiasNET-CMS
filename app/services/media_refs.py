"""Dove sono usati i media (D-78, D-79).

- `document_refs`: i media di un documento di pagina (blocchi + `seo.og_image_media_id`);
- `check_document`: alla pubblicazione, ogni media esiste, è del tipo giusto e, se immagine,
  ha il testo alternativo. La bozza e l'anteprima non lo chiamano mai (D-46);
- `pages_using`: le pagine non cestinate che usano un media (pubblicata, bozza, programmata).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Any

from sqlalchemy import String, cast, or_, select

from app.extensions import db
from app.models.entry import Entry, EntryDraft, EntryStatus
from app.models.media import Media, MediaKind
from app.models.page import Block, Page, PageDraft, PageRevision, PageStatus, RevisionKind
from app.services import collections, entries, settings_store
from app.services.blocks import FieldError, MediaRef, get_registry
from app.services.page_paths import live
from app.services.theme import active_theme

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
    return check_refs(document_refs(document))


def check_refs(refs: Sequence[MediaRef]) -> list[FieldError]:
    """Ogni media esiste, è del tipo giusto e, se immagine, ha il testo alternativo."""
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


# Fonti di "in uso": pagine (pubblicate, bozze, programmate); poi notizie e impostazioni.
SOURCES = (_published, _drafts, _scheduled)


def _entry_documents(media_id: int) -> Iterator[tuple[Entry, str, Any]]:
    """Solo le voci delle raccolte con immagini che nominano l'id da qualche parte: il controllo
    vero lo fa poi lo schema (il filtro sul testo serve solo a non leggere tutto)."""
    theme = active_theme()
    keys = [key for key in theme.collections if collections.has_media(theme, key)]
    if not keys:
        return
    needle = f"%{media_id}%"
    mentions = or_(
        cast(Entry.fields_json, String).like(needle),
        cast(Entry.seo_json, String).like(needle),
        cast(Entry.scheduled_json, String).like(needle),
    )
    query = select(Entry).where(Entry.deleted_at.is_(None), Entry.collection.in_(keys), mentions)
    for entry in db.session.execute(query).scalars():
        where = "published" if entry.status == EntryStatus.PUBLISHED else "unpublished"
        yield entry, where, entries.published_document(entry)
        if entry.scheduled_json is not None:
            yield entry, "scheduled", entry.scheduled_json
    drafts = db.session.execute(
        select(EntryDraft, Entry)
        .join(Entry, Entry.id == EntryDraft.entry_id)
        .where(
            Entry.deleted_at.is_(None),
            Entry.collection.in_(keys),
            cast(EntryDraft.data_json, String).like(needle),
        )
    )
    for draft, entry in drafts:
        yield entry, "draft", draft.data_json


def _entries_using(media_id: int) -> Iterator[tuple[Entry, str]]:
    """Le notizie (pubblicate, bozze, programmate) che usano un media (D-147)."""
    theme = active_theme()
    for entry, where, document in _entry_documents(media_id):
        refs = collections.media_refs(theme, entry.collection, document)
        if any(ref.media_id == media_id for ref in refs):
            yield entry, where


def _is_logo(media_id: int) -> bool:
    return settings_store.stored("site").get("logo") == media_id


def pages_using(media_id: int) -> list[dict[str, Any]]:
    """Pagine (e impostazioni del sito, D-143) che usano un media."""
    seen: set[tuple[int, str]] = set()
    usages: list[dict[str, Any]] = []
    if _is_logo(media_id):
        usages.append(
            {"page_id": None, "title": "Impostazioni del sito", "path": "", "where": "settings"}
        )
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
    entry_seen: set[tuple[int, str]] = set()
    for entry, where in _entries_using(media_id):
        if (entry.id, where) in entry_seen:
            continue
        entry_seen.add((entry.id, where))
        usages.append(
            {
                "page_id": None,
                "entry_id": entry.id,
                "title": entry.title,
                "path": "",
                "where": where,
            }
        )
        if len(usages) >= MAX_USAGES:
            return usages
    return usages


def used_by_online_pages(media_id: int) -> bool:
    """Usato da una pagina online o programmata (per non togliere l'alt, D-77): si guardano
    solo queste due fonti e ci si ferma al primo caso, senza il tetto di MAX_USAGES."""
    online = (where for _page, where in _published(media_id) if where == "published")
    if _is_logo(media_id):  # il logo è sempre online
        return True
    if next(online, None) is not None or next(_scheduled(media_id), None) is not None:
        return True
    live_entries = (w for _e, w in _entries_using(media_id) if w in ("published", "scheduled"))
    return next(live_entries, None) is not None
