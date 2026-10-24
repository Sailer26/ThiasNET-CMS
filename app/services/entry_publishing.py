"""Pubblica, programma, ritira le voci delle raccolte (D-47, D-147).

Come le pagine: pubblicare rivalida il documento contro il tema attuale (D-46) e i media che
usa (D-77), copia titolo, campi e SEO nella voce, scrive una versione e toglie la bozza.
Le programmazioni scadute le pubblica il comando `publish-scheduled` e, se il cron è in
ritardo, la prima visita al sito (`publish_due`).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import current_app
from sqlalchemy import func, select

from app.extensions import db
from app.models.entry import Entry, EntryDraft, EntryStatus
from app.models.types import utcnow
from app.models.user import User
from app.services import audit, collections, entity_revisions, entries, media_refs, page_cache
from app.services.blocks import Mode
from app.services.content import invalid
from app.services.errors import ServiceError
from app.services.permissions import Permission, require
from app.services.publishing import MAX_FAILURE_DETAILS, parse_publish_at
from app.services.theme import active_theme

Document = dict[str, Any]
DUE_KEY = "thiasnet_entries_due"
RETRY_AFTER = timedelta(seconds=60)


def _source(entry: Entry, draft_version: int) -> tuple[Any, bool]:
    """Il documento da pubblicare: la bozza, oppure quello della voce ritirata o recuperata."""
    draft = entries.load_draft(entry.id)
    if draft is not None:
        if draft.version != draft_version:
            raise entries.draft_conflict(draft)
        return draft.data_json, True
    if draft_version != 0:
        raise entries.draft_conflict(None)
    if entry.status == EntryStatus.PUBLISHED:
        raise ServiceError("no_draft", "Non ci sono modifiche da pubblicare", 409)
    return entries.published_document(entry), False


def validated(entry: Entry, source: Any) -> Document:
    """Validazione completa per andare online: campi (D-46) e media (D-77, D-78)."""
    theme = active_theme()
    document = collections.validate(theme, entry.collection, source, Mode.PUBLISH)
    problems = media_refs.check_refs(collections.media_refs(theme, entry.collection, document))
    if problems:
        raise invalid(problems)
    return document


def _apply(entry: Entry, document: Document, actor_id: int | None, now: datetime) -> None:
    theme = active_theme()
    entries.bump_version(entry, entry.version)
    entry.title = document["title"]
    entry.fields_json = copy.deepcopy(document["fields"])
    entry.seo_json = copy.deepcopy(document["seo"])
    entry.status, entry.published_at, entry.publish_at = EntryStatus.PUBLISHED, now, None
    entry.scheduled_json = None
    entry.scheduled_by = None
    entry.sort_at = collections.sort_moment(theme, entry.collection, document["fields"], now)
    entry.updated_by = actor_id
    entity_revisions.record(entries.REVISION_TYPE, str(entry.id), document, actor_id)
    page_cache.mark_changed()


def publish(actor: User, entry: Entry, draft_version: int) -> Entry:
    require(actor, Permission.PUBLISH)
    source, has_draft = _source(entry, draft_version)
    document = validated(entry, source)
    cancelled = entry.scheduled_json is not None
    _apply(entry, document, actor.id, utcnow())
    if has_draft:
        entries.drop_draft(entry.id, draft_version)
    audit.record(
        "entry.published",
        actor_id=actor.id,
        entity="entry",
        entity_id=entry.id,
        diff={"title": document["title"], "schedule_cancelled": cancelled},
    )
    db.session.commit()
    return entry


def schedule(actor: User, entry: Entry, draft_version: int, publish_at: str) -> Entry:
    """Congela il documento nella voce; la bozza resta modificabile (D-47)."""
    require(actor, Permission.PUBLISH)
    when = parse_publish_at(publish_at, utcnow())
    source, _has_draft = _source(entry, draft_version)
    document = validated(entry, source)
    entries.bump_version(entry, entry.version)
    entry.scheduled_json = copy.deepcopy(document)
    entry.scheduled_by, entry.publish_at = actor.id, when
    if entry.status != EntryStatus.PUBLISHED:  # una voce online resta online fino all'ora
        entry.status = EntryStatus.SCHEDULED
    entry.updated_by = actor.id
    page_cache.mark_changed()  # la data nuova: le visite ricontrollano le scadenze
    audit.record(
        "entry.scheduled",
        actor_id=actor.id,
        entity="entry",
        entity_id=entry.id,
        diff={"publish_at": when.isoformat()},
    )
    db.session.commit()
    return entry


def _offline_schedule(entry: Entry) -> None:
    entry.publish_at = None
    entry.scheduled_json = None
    entry.scheduled_by = None
    if entry.status == EntryStatus.SCHEDULED:
        entry.status = EntryStatus.DRAFT


def unschedule(actor: User, entry: Entry, version: int) -> Entry:
    require(actor, Permission.PUBLISH)
    if version != entry.version:
        raise entries.conflict(entry)
    if entry.scheduled_json is None:
        raise ServiceError("not_scheduled", "La notizia non ha una pubblicazione programmata", 409)
    entries.bump_version(entry, version)
    _offline_schedule(entry)
    entry.updated_by = actor.id
    page_cache.mark_changed()
    audit.record("entry.unscheduled", actor_id=actor.id, entity="entry", entity_id=entry.id)
    db.session.commit()
    return entry


def unpublish(actor: User, entry: Entry, version: int) -> Entry:
    """La voce va offline; il contenuto resta per ripubblicarla."""
    require(actor, Permission.PUBLISH)
    if version != entry.version:
        raise entries.conflict(entry)
    if entry.status != EntryStatus.PUBLISHED:
        raise ServiceError("not_published", "La notizia non è online", 409)
    entries.bump_version(entry, version)
    _offline_schedule(entry)
    entry.status, entry.published_at = EntryStatus.DRAFT, None
    entry.updated_by = actor.id
    page_cache.mark_changed()
    audit.record("entry.unpublished", actor_id=actor.id, entity="entry", entity_id=entry.id)
    db.session.commit()
    return entry


# --- Programmazioni scadute ----------------------------------------------------------------


def _fail(entry: Entry, exc: ServiceError) -> None:
    """Contenuto non più valido per il tema: niente pubblicazione e niente tentativi ogni
    minuto; il contenuto programmato torna nella bozza se non ce n'è una."""
    snapshot = entry.scheduled_json
    entries.bump_version(entry, entry.version)
    _offline_schedule(entry)
    if snapshot is not None and entries.load_draft(entry.id) is None:
        db.session.add(EntryDraft(entry_id=entry.id, data_json=snapshot, author_id=None))
    problems = exc.details if isinstance(exc.details, list) else [exc.message]
    audit.record(
        "entry.schedule_failed",
        actor_id=None,
        entity="entry",
        entity_id=entry.id,
        diff={"errors": problems[:MAX_FAILURE_DETAILS]},
    )
    db.session.commit()


def _publish_scheduled(entry: Entry, now: datetime) -> bool:
    snapshot, author_id = entry.scheduled_json, entry.scheduled_by
    if snapshot is None:  # dati incoerenti: la data resta senza istantanea
        _offline_schedule(entry)
        db.session.commit()
        return False
    try:
        document = validated(entry, snapshot)
    except ServiceError as exc:
        _fail(entry, exc)
        return False
    _apply(entry, document, author_id, now)
    draft = entries.load_draft(entry.id)
    if draft is not None and draft.data_json == snapshot:
        db.session.delete(draft)  # nessuna modifica dopo la programmazione
    audit.record(
        "entry.published",
        actor_id=None,
        entity="entry",
        entity_id=entry.id,
        diff={"title": document["title"], "scheduled": True},
    )
    db.session.commit()
    return True


@dataclass(frozen=True)
class DueResult:
    published: int
    failed: int


def run_due(now: datetime) -> DueResult:
    """Pubblica le voci con programmazione scaduta; un errore su una non ferma le altre."""
    query = (
        select(Entry.id)
        .where(Entry.deleted_at.is_(None), Entry.publish_at.is_not(None), Entry.publish_at <= now)
        .order_by(Entry.publish_at, Entry.id)
    )
    published = failed = 0
    for entry_id in list(db.session.execute(query).scalars()):
        try:
            entry = db.session.get(Entry, entry_id)
            if entry is not None and _publish_scheduled(entry, now):
                published += 1
        except ServiceError as exc:  # di solito un altro processo l'ha appena pubblicata (409)
            db.session.rollback()
            current_app.logger.warning("publish-scheduled: notizia %s: %s", entry_id, exc.code)
            failed += 1
        except Exception:  # un errore inatteso su una voce non deve fermare le altre
            db.session.rollback()
            current_app.logger.exception("publish-scheduled: notizia %s non pubblicata", entry_id)
            failed += 1
    return DueResult(published=published, failed=failed)


@dataclass(frozen=True)
class _Due:
    generation: int
    next_due: datetime | None


def publish_due(generation: int) -> bool:
    """Dalla route pubblica: il prossimo "publish_at" si ricorda per processo, così le visite
    normali non fanno query in più finché la generazione della cache non cambia (D-146)."""
    now = datetime.now(UTC)
    known = current_app.extensions.get(DUE_KEY)
    if (
        isinstance(known, _Due)
        and known.generation == generation
        and (known.next_due is None or now < known.next_due)
    ):
        return False
    result = run_due(now)
    published = result.published > 0
    upcoming = select(func.min(Entry.publish_at)).where(
        Entry.deleted_at.is_(None), Entry.publish_at > now
    )
    next_due: datetime | None = db.session.execute(upcoming).scalar_one()
    if result.failed:  # una voce che non riesce: si riprova tra un po', non a ogni visita
        retry = now + RETRY_AFTER
        next_due = retry if next_due is None else min(next_due, retry)
    current = page_cache.current_generation() if published else generation
    current_app.extensions[DUE_KEY] = _Due(current, next_due)
    return published
