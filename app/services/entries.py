"""Voci delle raccolte (D-147): creazione, indirizzo, bozza, cestino, elenco del pannello.

Come le pagine (D-38, D-44, D-48): la bozza è un documento unico salvato con versione;
le azioni su voci online o programmate chiedono anche `content.publish`. Pubblicazione e
programmazione stanno in `entry_publishing.py`.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from types import EllipsisType
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import set_committed_value

from app.extensions import db
from app.models.entry import Entry, EntryDraft, EntryStatus
from app.models.page import SLUG_MAX_LENGTH, TITLE_MAX_LENGTH, Page, PageStatus
from app.models.revision import EntityRevision
from app.models.types import utcnow
from app.models.user import User
from app.services import audit, collections, entity_revisions, page_cache
from app.services.authors import display_name
from app.services.blocks import Mode
from app.services.errors import ServiceError, not_found, version_conflict
from app.services.page_paths import HOME_PATH, live, public_path
from app.services.permissions import Permission, require
from app.services.sanitize import clean_line
from app.services.slugs import slugify, validate_slug
from app.services.sql import rows_affected
from app.services.theme import Theme, active_theme

ENTRY_NOT_FOUND = "Notizia non trovata"
SUBJECT = "questa notizia"
FALLBACK_SLUG = "notizia"
MAX_SLUG_ATTEMPTS = 500
ONLINE = frozenset({EntryStatus.PUBLISHED, EntryStatus.SCHEDULED})
SLUG_INDEX_MARKERS = ("uq_entries_locale_collection_slug", "entries.locale, entries.collection")
GROUP_INDEX_MARKERS = ("uq_entries_group_locale", "entries.translation_group, entries.locale")
REVISION_TYPE = "entry"
Document = dict[str, Any]


def is_online(entry: Entry) -> bool:
    return entry.status in ONLINE or entry.publish_at is not None


def get_entry(entry_id: int) -> Entry:
    entry = db.session.get(Entry, entry_id)
    if entry is None or entry.deleted_at is not None:
        raise not_found(ENTRY_NOT_FOUND)
    return entry


def get_trashed(entry_id: int) -> Entry:
    entry = db.session.get(Entry, entry_id)
    if entry is None or entry.deleted_at is None:
        raise not_found(ENTRY_NOT_FOUND)
    return entry


def conflict(entry: Entry) -> ServiceError:
    return version_conflict(entry.version, entry.updated_by, entry.updated_at, SUBJECT)


def bump_version(entry: Entry, expected: int) -> None:
    """D-44: UPDATE condizionato; se qualcun altro ha salvato prima → 409."""
    if entry.version != expected:
        raise conflict(entry)
    statement = (
        update(Entry)
        .where(Entry.id == entry.id, Entry.version == expected)
        .values(version=expected + 1)
        .execution_options(synchronize_session=False)
    )
    if rows_affected(statement) != 1:
        db.session.rollback()
        raise conflict(db.session.get_one(Entry, entry.id))
    set_committed_value(entry, "version", expected + 1)


# --- Indirizzo -----------------------------------------------------------------------


def listing_page(theme: Theme, collection: str, locale: str, *, online: bool) -> Page | None:
    """La pagina elenco della raccolta (D-149): una per lingua, con il layout che la elenca."""
    layout = theme.listing_layout(collection)
    if layout is None:
        return None
    query = select(Page).where(live(), Page.locale == locale, Page.layout == layout)
    if online:
        query = query.where(Page.status == PageStatus.PUBLISHED)
    return db.session.execute(query.order_by(Page.id).limit(1)).scalar_one_or_none()


def entry_url(listing: Page, slug: str, theme: Theme) -> str:
    base = "" if listing.path == HOME_PATH else listing.path
    return public_path(listing.locale, f"{base}/{slug}", theme)


def public_url(entry: Entry, theme: Theme) -> str | None:
    listing = listing_page(theme, entry.collection, entry.locale, online=False)
    return None if listing is None else entry_url(listing, entry.slug, theme)


def _slug_taken(collection: str, locale: str, slug: str, exclude: int | None = None) -> bool:
    query = select(Entry.id).where(
        Entry.deleted_at.is_(None),
        Entry.collection == collection,
        Entry.locale == locale,
        Entry.slug == slug,
    )
    if exclude is not None:
        query = query.where(Entry.id != exclude)
    return db.session.execute(query.limit(1)).first() is not None


def _free_slug(base: str, collection: str, locale: str) -> str:
    for attempt in range(1, MAX_SLUG_ATTEMPTS + 1):
        suffix = "" if attempt == 1 else f"-{attempt}"
        candidate = base[: SLUG_MAX_LENGTH - len(suffix)].rstrip("-") + suffix
        if not _slug_taken(collection, locale, candidate):
            return candidate
    raise ServiceError("slug_taken", "Non trovo un indirizzo libero: indicane uno", 409)


def _slug_taken_error() -> ServiceError:
    return ServiceError("slug_taken", "Esiste già una notizia con questo indirizzo", 409)


def _commit_unique() -> None:
    """Con richieste parallele decide l'indice unico dello slug: 409 invece di 500."""
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        if any(marker in str(exc.orig) for marker in SLUG_INDEX_MARKERS):
            raise _slug_taken_error() from exc
        if any(marker in str(exc.orig) for marker in GROUP_INDEX_MARKERS):
            raise translation_exists() from exc
        raise


# --- Creazione e indirizzo ----------------------------------------------------------------


def _title(raw: str) -> str:
    title = clean_line(raw)
    if not title or len(title) > TITLE_MAX_LENGTH:
        raise ServiceError(
            "invalid_title", f"Il titolo è obbligatorio (massimo {TITLE_MAX_LENGTH})", 422
        )
    return title


def empty_document(title: str) -> Document:
    return {"title": title, "fields": {}, "seo": {}}


def translation_exists() -> ServiceError:
    return ServiceError("translation_exists", "Questa lingua ha già la sua traduzione", 409)


def translation_taken(group: str, locale: str, exclude: int | None = None) -> bool:
    query = select(Entry.id).where(
        Entry.deleted_at.is_(None), Entry.translation_group == group, Entry.locale == locale
    )
    if exclude is not None:
        query = query.where(Entry.id != exclude)
    return db.session.execute(query.limit(1)).first() is not None


def create(
    actor: User,
    collection: str,
    *,
    title: str,
    locale: str | None = None,
    translation_group: str | None = None,
) -> Entry:
    theme = active_theme()
    collections.spec(theme, collection)
    locale = locale or theme.locales[0]
    if locale not in theme.locales:
        raise ServiceError("unknown_locale", "Lingua non attiva in questo sito", 422)
    clean_title = _title(title)
    slug = _free_slug(slugify(clean_title) or FALLBACK_SLUG, collection, locale)
    entry = Entry(
        collection=collection,
        locale=locale,
        translation_group=translation_group or str(uuid.uuid4()),
        slug=slug,
        title=clean_title,
        fields_json={},
        seo_json={},
        created_by=actor.id,
        updated_by=actor.id,
    )
    db.session.add(entry)
    try:  # due creazioni con lo stesso titolo nello stesso istante: 409, non 500
        db.session.flush()
    except IntegrityError as exc:
        db.session.rollback()
        if any(marker in str(exc.orig) for marker in SLUG_INDEX_MARKERS):
            raise _slug_taken_error() from exc
        if any(marker in str(exc.orig) for marker in GROUP_INDEX_MARKERS):
            raise translation_exists() from exc
        raise
    db.session.add(
        EntryDraft(entry_id=entry.id, data_json=empty_document(clean_title), author_id=actor.id)
    )
    audit.record(
        "entry.created",
        actor_id=actor.id,
        entity="entry",
        entity_id=entry.id,
        diff={"collection": collection, "title": clean_title, "slug": slug},
    )
    _commit_unique()
    return entry


def change_slug(actor: User, entry: Entry, version: int, slug: str) -> Entry:
    """D-152: l'indirizzo cambia solo finché la notizia non è online (niente link rotti)."""
    if version != entry.version:
        raise conflict(entry)
    if is_online(entry):
        raise ServiceError(
            "slug_fixed", "La notizia è già online: il suo indirizzo non si cambia", 409
        )
    validate_slug(slug)
    if slug == entry.slug:
        return entry
    if _slug_taken(entry.collection, entry.locale, slug, exclude=entry.id):
        raise _slug_taken_error()
    bump_version(entry, version)
    diff = {"slug": [entry.slug, slug]}
    entry.slug, entry.updated_by = slug, actor.id
    audit.record(
        "entry.slug_changed", actor_id=actor.id, entity="entry", entity_id=entry.id, diff=diff
    )
    _commit_unique()
    return entry


# --- Cestino -------------------------------------------------------------------------


def trash(actor: User, entry: Entry, version: int) -> Entry:
    """D-43: si cestina, non si elimina; la notizia va subito offline."""
    if is_online(entry):
        require(actor, Permission.PUBLISH)
    previous = entry.status
    bump_version(entry, version)
    entry.deleted_at, entry.deleted_by, entry.updated_by = utcnow(), actor.id, actor.id
    entry.status, entry.publish_at, entry.published_at = EntryStatus.DRAFT, None, None
    entry.scheduled_json = None
    entry.scheduled_by = None
    page_cache.mark_changed()
    audit.record(
        "entry.trashed",
        actor_id=actor.id,
        entity="entry",
        entity_id=entry.id,
        diff={"slug": entry.slug, "status": previous},
    )
    db.session.commit()
    return entry


def restore(actor: User, entry: Entry, version: int) -> Entry:
    """Torna come bozza non pubblicata, se il suo indirizzo è ancora libero."""
    if _slug_taken(entry.collection, entry.locale, entry.slug, exclude=entry.id):
        raise _slug_taken_error()
    if translation_taken(entry.translation_group, entry.locale, exclude=entry.id):
        raise translation_exists()  # D-161
    bump_version(entry, version)
    entry.deleted_at = None
    entry.deleted_by = None
    entry.status, entry.updated_by = EntryStatus.DRAFT, actor.id
    audit.record("entry.restored", actor_id=actor.id, entity="entry", entity_id=entry.id)
    _commit_unique()
    return entry


# --- Bozza ---------------------------------------------------------------------------


def load_draft(entry_id: int) -> EntryDraft | None:
    return db.session.get(EntryDraft, entry_id)


def published_document(entry: Entry) -> Document:
    return {
        "title": entry.title,
        "fields": dict(entry.fields_json or {}),
        "seo": dict(entry.seo_json or {}),
    }


def draft_view(entry: Entry) -> dict[str, Any]:
    draft = load_draft(entry.id)
    if draft is None:
        return {
            "version": 0,
            "data": published_document(entry),
            "from_published": True,
            "author_id": None,
            "updated_at": None,
        }
    return {
        "version": draft.version,
        "data": draft.data_json,
        "from_published": False,
        "author_id": draft.author_id,
        "updated_at": draft.updated_at.isoformat(),
    }


def draft_conflict(draft: EntryDraft | None) -> ServiceError:
    if draft is None:
        return version_conflict(0, None, None, SUBJECT)
    return version_conflict(draft.version, draft.author_id, draft.updated_at, SUBJECT)


def _write_draft(actor: User, entry: Entry, expected: int, document: Document) -> int:
    draft = load_draft(entry.id)
    if expected == 0:
        if draft is not None:
            raise draft_conflict(draft)
        db.session.add(EntryDraft(entry_id=entry.id, data_json=document, author_id=actor.id))
        try:
            db.session.flush()
        except IntegrityError as exc:  # un'altra richiesta l'ha appena creata
            db.session.rollback()
            raise draft_conflict(load_draft(entry.id)) from exc
        return 1
    if draft is None or draft.version != expected:
        raise draft_conflict(draft)
    statement = (
        update(EntryDraft)
        .where(EntryDraft.entry_id == entry.id, EntryDraft.version == expected)
        .values(data_json=document, version=expected + 1, author_id=actor.id, updated_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    if rows_affected(statement) != 1:
        db.session.rollback()
        raise draft_conflict(load_draft(entry.id))
    db.session.expire(draft)
    return expected + 1


def store_draft(actor: User, entry: Entry, expected: int, document: Any) -> int:
    clean = collections.validate(active_theme(), entry.collection, document, Mode.DRAFT)
    version = _write_draft(actor, entry, expected, clean)
    db.session.commit()
    return version


def drop_draft(entry_id: int, draft_version: int) -> None:
    """Toglie la bozza appena pubblicata; se nel frattempo qualcuno l'ha salvata → 409."""
    statement = delete(EntryDraft).where(
        EntryDraft.entry_id == entry_id, EntryDraft.version == draft_version
    )
    if rows_affected(statement) != 1:
        db.session.rollback()
        raise draft_conflict(load_draft(entry_id))


def discard_draft(actor: User, entry: Entry, expected: int) -> None:
    draft = load_draft(entry.id)
    if draft is None:
        raise ServiceError("no_draft", "Non ci sono modifiche da annullare", 409)
    if draft.version != expected:
        raise draft_conflict(draft)
    drop_draft(entry.id, expected)
    audit.record("entry.draft_discarded", actor_id=actor.id, entity="entry", entity_id=entry.id)
    db.session.commit()


# --- Letture per il pannello --------------------------------------------------------------


def _iso(value: Any) -> str | None:
    return None if value is None else value.isoformat()


def serialize(
    entry: Entry,
    theme: Theme,
    *,
    has_draft: bool | None = None,
    drafts: Mapping[int, EntryDraft] | None = None,
    listing: Page | EllipsisType | None = ...,
) -> dict[str, Any]:
    """`listing` già cercata evita una query per riga nell'elenco del pannello."""
    if drafts is not None:
        drafted = entry.id in drafts
    else:
        drafted = load_draft(entry.id) is not None if has_draft is None else has_draft
    found = (
        listing_page(theme, entry.collection, entry.locale, online=False)
        if isinstance(listing, EllipsisType)
        else listing
    )
    return {
        "id": entry.id,
        "collection": entry.collection,
        "locale": entry.locale,
        "slug": entry.slug,
        "title": entry.title,
        "status": entry.status,
        "version": entry.version,
        "publish_at": _iso(entry.publish_at),
        "published_at": _iso(entry.published_at),
        "sort_at": _iso(entry.sort_at),
        "updated_at": _iso(entry.updated_at),
        "updated_by": entry.updated_by,
        "deleted_at": _iso(entry.deleted_at),
        "has_draft": drafted,
        "url": None if found is None else entry_url(found, entry.slug, theme),
        "schedule": _schedule(entry, drafts),
    }


def _schedule(
    entry: Entry, drafts: Mapping[int, EntryDraft] | None = None
) -> dict[str, Any] | None:
    """La programmazione in attesa; `draft_newer`: la bozza è cambiata dopo (D-122)."""
    if entry.scheduled_json is None or entry.publish_at is None:
        return None
    draft = load_draft(entry.id) if drafts is None else drafts.get(entry.id)
    return {
        "publish_at": _iso(entry.publish_at),
        "author_name": display_name(entry.scheduled_by),
        "draft_newer": draft is not None and draft.data_json != entry.scheduled_json,
    }


def panel_list(
    theme: Theme,
    collection: str,
    *,
    page: int,
    per_page: int,
    trash: bool,
    locale: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Le voci di una raccolta per il pannello: le più recenti in cima."""
    collections.spec(theme, collection)
    locale = locale or theme.locales[0]  # D-159: la lingua scelta nel pannello
    deleted = Entry.deleted_at.is_not(None) if trash else Entry.deleted_at.is_(None)
    where = (Entry.collection == collection, Entry.locale == locale, deleted)
    total = db.session.execute(select(func.count()).select_from(Entry).where(*where)).scalar_one()
    order = (Entry.sort_at.desc().nulls_first(), Entry.updated_at.desc(), Entry.id.desc())
    query = select(Entry).where(*where).order_by(*order).offset((page - 1) * per_page)
    rows = list(db.session.execute(query.limit(per_page)).scalars())
    drafts = {
        draft.entry_id: draft
        for draft in db.session.execute(
            select(EntryDraft).where(EntryDraft.entry_id.in_([e.id for e in rows]))
        ).scalars()
    }
    listing = listing_page(theme, collection, locale, online=False)
    found = [serialize(e, theme, drafts=drafts, listing=listing) for e in rows]
    return found, int(total)


# --- Versioni (D-40, D-42) -----------------------------------------------------------------


def record_revision(entry: Entry, kind: str, document: Document, author_id: int | None) -> None:
    """Una versione con il suo tipo ("published" o "draft"); non fa commit."""
    snapshot = {**document, "kind": kind}
    entity_revisions.record(REVISION_TYPE, str(entry.id), snapshot, author_id)


def _snapshot(revision: EntityRevision) -> Document:
    data = revision.snapshot_json if isinstance(revision.snapshot_json, dict) else {}
    return {key: value for key, value in data.items() if key != "kind"}


def serialize_revision(revision: EntityRevision, *, with_snapshot: bool = False) -> dict[str, Any]:
    data = revision.snapshot_json if isinstance(revision.snapshot_json, dict) else {}
    found: dict[str, Any] = {
        "id": revision.id,
        "kind": data.get("kind", "published"),
        "author_id": revision.author_id,
        "author_name": display_name(revision.author_id),  # un editor non legge gli utenti (D-92)
        "title": str(data.get("title") or ""),
        "created_at": revision.created_at.isoformat(),
    }
    if with_snapshot:
        found["snapshot"] = _snapshot(revision)
    return found


def revisions(entry: Entry) -> list[dict[str, Any]]:
    return [
        serialize_revision(revision)
        for revision in entity_revisions.history(REVISION_TYPE, str(entry.id))
    ]


def revision(entry: Entry, revision_id: int) -> EntityRevision:
    found = entity_revisions.get(REVISION_TYPE, str(entry.id), revision_id)
    if found is None:
        raise not_found("Versione non trovata")
    return found


def restore_revision(actor: User, entry: Entry, revision_id: int, draft_version: int) -> int:
    """D-42: la versione torna nella bozza, mai online. La bozza di adesso non va persa (D-40)."""
    theme = active_theme()
    chosen = revision(entry, revision_id)
    snapshot = _snapshot(chosen)
    # Un campo che il tema non ha più non deve bloccare il ripristino del resto (D-53).
    raw_fields = snapshot.get("fields")
    fields: dict[str, Any] = raw_fields if isinstance(raw_fields, dict) else {}
    snapshot = {**snapshot, "fields": collections.lenient(theme, entry.collection, fields)}
    clean = collections.validate(theme, entry.collection, snapshot, Mode.DRAFT)
    current = load_draft(entry.id)
    previous = (
        current.data_json if current is not None and current.version == draft_version else None
    )
    version = _write_draft(actor, entry, draft_version, clean)  # 409 qui: nulla da registrare
    if previous is not None:
        record_revision(entry, "draft", previous, actor.id)
    audit.record(
        "entry.revision_restored",
        actor_id=actor.id,
        entity="entry",
        entity_id=entry.id,
        diff={"revision_id": chosen.id, "from_version": draft_version},
    )
    db.session.commit()
    return version
