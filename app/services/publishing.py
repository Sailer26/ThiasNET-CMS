"""Pubblica, programma, ritira (D-16, D-38, D-47).

Pubblicare = rivalidare il documento contro il tema attuale, sostituire i `blocks` in una
transazione, scrivere una revisione, cancellare la bozza. `publish_due` è usato dal comando
`flask publish-scheduled` (cron ogni minuto) e, dalla Fase 3, da `ensure_due` a richiesta.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import current_app
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.page import Block, Page, PageDraft, PageRevision, PageStatus, RevisionKind
from app.models.types import utcnow
from app.models.user import User
from app.services import audit, drafts, media_refs, page_cache, pages, revisions
from app.services.blocks import FieldError, Mode
from app.services.content import invalid as content_invalid
from app.services.content import validate_document
from app.services.errors import ServiceError, version_conflict
from app.services.permissions import Permission, require
from app.services.sql import rows_affected
from app.services.theme import active_theme

MAX_SCHEDULE_AHEAD = timedelta(days=366)
MAX_FAILURE_DETAILS = 20
Document = dict[str, Any]


@dataclass(frozen=True)
class DueResult:
    published: int
    failed: int


def _source(page: Page, draft_version: int) -> tuple[Any, PageDraft | None]:
    """Documento da pubblicare: la bozza, oppure il contenuto rimasto nei blocchi di una
    pagina ritirata o recuperata dal cestino (che si ripubblica senza toccare nulla)."""
    draft = drafts.load(page.id)
    if draft is not None:
        if draft.version != draft_version:
            raise drafts.conflict(draft)
        return draft.data_json, draft
    if draft_version != 0:
        raise drafts.conflict(None)
    if page.status == PageStatus.PUBLISHED:
        raise ServiceError("no_draft", "Non ci sono modifiche da pubblicare", 409)
    return drafts.published_document(page), None


def _problems(source: Any) -> tuple[Document | None, list[FieldError]]:
    """Validazione completa per andare online: contenuto e tema (D-46), poi i media usati
    esistono, sono del tipo giusto e le immagini hanno il testo alternativo (D-77, D-78).
    Gli errori dei campi tornano in una lista; gli altri (es. 413) si sollevano com'erano."""
    try:
        document = validate_document(active_theme(), source, Mode.PUBLISH)
    except ServiceError as error:
        if error.code != "invalid_content":
            raise
        found = [FieldError(d["path"], d["code"], d["message"]) for d in error.details or []]
        # Anche i media del documento non valido: il cliente vede tutto in una volta sola.
        media = [e for e in media_refs.check_document(source) if e not in found]
        return None, found + media
    return document, media_refs.check_document(document)


def problems(source: Any) -> tuple[Document | None, list[FieldError]]:
    """Per il controllo prima di pubblicare (D-135): la stessa validazione di `publish`,
    così i due non possono dire cose diverse; non solleva mai."""
    try:
        return _problems(source)
    except ServiceError as error:
        return None, [FieldError("", error.code, error.message)]


def _validated(source: Any, page: Page | None = None) -> Document:
    document, found = _problems(source)
    if found or document is None:
        raise content_invalid(found)
    if page is not None:  # D-149: il layout di una pagina elenco ha le sue regole
        pages.check_listing(page, document["layout"], page.locale)
    return document


def _apply(page: Page, document: Document, actor_id: int | None, now: datetime) -> None:
    """Il documento diventa la versione pubblicata: blocchi sostituiti, mai accumulati.
    Pagina e blocchi ricevono copie proprie, separate dall'istantanea della revisione."""
    pages.bump_version(page, page.version)
    db.session.execute(delete(Block).where(Block.page_id == page.id))
    db.session.add_all(
        Block(
            page_id=page.id,
            uid=block["uid"],
            zone=zone,
            type=block["type"],
            variant=block["variant"],
            data_json=copy.deepcopy(block["data"]),
            sort=position,
        )
        for zone, blocks in document["zones"].items()
        for position, block in enumerate(blocks)
    )
    page.title, page.layout = document["title"], document["layout"]
    page.seo_json = copy.deepcopy(document["seo"])
    page.status, page.published_at, page.publish_at = PageStatus.PUBLISHED, now, None
    page.updated_by = actor_id
    page_cache.mark_changed()


def _drop_draft(page_id: int, draft_version: int) -> None:
    statement = delete(PageDraft).where(
        PageDraft.page_id == page_id, PageDraft.version == draft_version
    )
    if rows_affected(statement) != 1:  # salvata da qualcun altro mentre pubblicavamo
        db.session.rollback()
        raise drafts.conflict(drafts.load(page_id))


def publish(actor: User, page: Page, draft_version: int) -> Page:
    require(actor, Permission.PUBLISH)
    source, draft = _source(page, draft_version)
    document = _validated(source, page)
    cancelled = revisions.cancel_schedule(page.id)
    _apply(page, document, actor.id, utcnow())
    revisions.add(page.id, RevisionKind.PUBLISHED, document, actor.id)
    if draft is not None:
        _drop_draft(page.id, draft_version)
    audit.record(
        "page.published",
        actor_id=actor.id,
        entity="page",
        entity_id=page.id,
        diff={"title": document["title"], "schedule_cancelled": cancelled},
    )
    revisions.prune(page.id)
    db.session.commit()
    return page


def parse_publish_at(raw: str, now: datetime) -> datetime:
    """ISO 8601 con fuso obbligatorio, nel futuro e al massimo a un anno (D-47)."""
    invalid = ServiceError(
        "invalid_publish_at", "Indica data e ora future (entro un anno), con il fuso orario", 422
    )
    try:
        when = datetime.fromisoformat(raw)
        if when.tzinfo is None or when.utcoffset() is None:
            raise invalid
        when = when.astimezone(UTC)
    except (ValueError, OverflowError):  # anni come 0001 o 9999 escono dall'intervallo
        raise invalid from None
    if not now < when <= now + MAX_SCHEDULE_AHEAD:
        raise invalid
    return when


def schedule(actor: User, page: Page, draft_version: int, publish_at: str) -> Page:
    """Congela il documento in una revisione `scheduled`; la bozza resta modificabile."""
    require(actor, Permission.PUBLISH)
    when = parse_publish_at(publish_at, utcnow())
    source, _draft = _source(page, draft_version)
    document = _validated(source, page)
    try:
        pages.bump_version(page, page.version)
        revisions.cancel_schedule(page.id)
        revisions.add(page.id, RevisionKind.SCHEDULED, document, actor.id)
        page.publish_at = when
        if page.status != PageStatus.PUBLISHED:  # una pagina online resta online fino all'ora
            page.status = PageStatus.SCHEDULED
        page.updated_by = actor.id
        audit.record(
            "page.scheduled",
            actor_id=actor.id,
            entity="page",
            entity_id=page.id,
            diff={"publish_at": when.isoformat()},
        )
        db.session.commit()
    except IntegrityError as exc:  # un'altra programmazione salvata nello stesso istante
        db.session.rollback()
        raise ServiceError(
            "schedule_conflict", "Un'altra programmazione è appena stata salvata: ricarica", 409
        ) from exc
    return page


def unschedule(actor: User, page: Page, version: int) -> Page:
    require(actor, Permission.PUBLISH)
    if version != page.version:
        raise version_conflict(page.version, page.updated_by, page.updated_at)
    if not revisions.cancel_schedule(page.id):
        raise ServiceError("not_scheduled", "La pagina non ha una pubblicazione programmata", 409)
    pages.bump_version(page, version)
    page.publish_at = None
    if page.status == PageStatus.SCHEDULED:
        page.status = PageStatus.DRAFT
    page.updated_by = actor.id
    audit.record("page.unscheduled", actor_id=actor.id, entity="page", entity_id=page.id)
    db.session.commit()
    return page


def unpublish(actor: User, page: Page, version: int) -> Page:
    """La pagina va offline; il contenuto resta (bozza o blocchi) per ripubblicarla."""
    require(actor, Permission.PUBLISH)
    if version != page.version:
        raise version_conflict(page.version, page.updated_by, page.updated_at)
    if page.status != PageStatus.PUBLISHED:
        raise ServiceError("not_published", "La pagina non è online", 409)
    pages.bump_version(page, version)
    revisions.add(page.id, RevisionKind.UNPUBLISHED, drafts.published_document(page), actor.id)
    revisions.cancel_schedule(page.id)
    page.status, page.published_at, page.publish_at = PageStatus.DRAFT, None, None
    page.updated_by = actor.id
    page_cache.mark_changed()
    audit.record("page.unpublished", actor_id=actor.id, entity="page", entity_id=page.id)
    revisions.prune(page.id)
    db.session.commit()
    return page


# --- Pubblicazione programmata -----------------------------------------------------------


def _claim(revision: PageRevision, values: dict[str, Any]) -> bool:
    """Prende in carico la revisione in attesa solo se nessun altro processo l'ha già fatto."""
    statement = (
        update(PageRevision)
        .where(PageRevision.id == revision.id, PageRevision.kind == RevisionKind.SCHEDULED)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    claimed = rows_affected(statement) == 1
    db.session.expire(revision)
    return claimed


def _offline_schedule(page: Page) -> None:
    page.publish_at = None
    if page.status == PageStatus.SCHEDULED:
        page.status = PageStatus.DRAFT


def _fail(page: Page, revision: PageRevision, exc: ServiceError, now: datetime) -> None:
    """Contenuto non più valido per il tema attuale: niente pubblicazione e niente tentativi
    ogni minuto. L'istantanea resta recuperabile come revisione `draft`."""
    if not _claim(revision, {"kind": RevisionKind.DRAFT, "created_at": now}):
        db.session.rollback()
        return
    pages.bump_version(page, page.version)
    _offline_schedule(page)
    problems = exc.details if isinstance(exc.details, list) else [exc.message]
    audit.record(
        "page.schedule_failed",
        actor_id=None,
        entity="page",
        entity_id=page.id,
        diff={"errors": problems[:MAX_FAILURE_DETAILS]},
    )
    db.session.commit()


def _publish_scheduled(page: Page, now: datetime) -> bool:
    """D-47: l'istantanea si pubblica a nome di chi l'ha programmata, senza ricontrollare
    i suoi permessi di oggi (li aveva quando ha scelto data e contenuto)."""
    revision = revisions.pending_schedule(page.id)
    if revision is None:  # dati incoerenti: la data resta senza istantanea
        _offline_schedule(page)
        db.session.commit()
        return False
    snapshot, author_id = revision.snapshot_json, revision.author_id
    try:
        document = _validated(snapshot, page)
    except ServiceError as exc:
        _fail(page, revision, exc, now)
        return False
    if not _claim(
        revision, {"kind": RevisionKind.PUBLISHED, "snapshot_json": document, "created_at": now}
    ):
        db.session.rollback()
        return False
    _apply(page, document, author_id, now)
    draft = drafts.load(page.id)
    if draft is not None and draft.data_json == snapshot:
        db.session.delete(draft)  # nessuna modifica dopo la programmazione
    audit.record(
        "page.published",
        actor_id=None,
        entity="page",
        entity_id=page.id,
        diff={"title": document["title"], "scheduled": True},
    )
    revisions.prune(page.id)
    db.session.commit()
    return True


def run_due(now: datetime) -> DueResult:
    """Pubblica le pagine con programmazione scaduta. Idempotente e isolato per pagina:
    un errore su una pagina viene registrato nel log e non blocca le altre."""
    query = (
        select(Page.id)
        .where(Page.deleted_at.is_(None), Page.publish_at.is_not(None), Page.publish_at <= now)
        .order_by(Page.publish_at, Page.id)
    )
    published = failed = 0
    for page_id in list(db.session.execute(query).scalars()):
        try:
            page = db.session.get(Page, page_id)
            if page is not None and _publish_scheduled(page, now):
                published += 1
        except Exception:  # un errore inatteso su una pagina non deve fermare le altre
            db.session.rollback()
            current_app.logger.exception("publish-scheduled: pagina %s non pubblicata", page_id)
            failed += 1
    return DueResult(published=published, failed=failed)


def publish_due(now: datetime) -> int:
    return run_due(now).published


def ensure_due(page: Page, now: datetime) -> bool:
    """Controllo a richiesta (Fase 3): se il cron è in ritardo pubblica subito questa pagina."""
    if page.publish_at is None or page.publish_at > now or page.deleted_at is not None:
        return False
    return _publish_scheduled(page, now)
