"""Revisioni delle pagine (D-40, D-42): storico, ripristino in bozza, potatura a 50.

Si creano solo con azioni esplicite (pubblica, programma, ritira, ripristina): mai con
l'autosave. La revisione `scheduled` in attesa è unica per pagina e non si pota.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select

from app.extensions import db
from app.models.page import Page, PageRevision, RevisionKind
from app.models.user import User
from app.services import audit, drafts
from app.services.blocks import Mode
from app.services.content import validate_document
from app.services.errors import not_found
from app.services.sql import rows_affected
from app.services.theme import active_theme

MAX_REVISIONS = 50
SCHEDULED = RevisionKind.SCHEDULED


def add(page_id: int, kind: str, snapshot: dict[str, Any], author_id: int | None) -> PageRevision:
    revision = PageRevision(page_id=page_id, kind=kind, snapshot_json=snapshot, author_id=author_id)
    db.session.add(revision)
    return revision


def pending_schedule(page_id: int) -> PageRevision | None:
    query = select(PageRevision).where(
        PageRevision.page_id == page_id, PageRevision.kind == SCHEDULED
    )
    return db.session.execute(query).scalar_one_or_none()


def cancel_schedule(page_id: int) -> bool:
    statement = delete(PageRevision).where(
        PageRevision.page_id == page_id, PageRevision.kind == SCHEDULED
    )
    return rows_affected(statement) > 0


def prune(page_id: int) -> None:
    """Tiene le ultime MAX_REVISIONS (la programmata in attesa non conta e non si tocca)."""
    old = (
        select(PageRevision.id)
        .where(PageRevision.page_id == page_id, PageRevision.kind != SCHEDULED)
        .order_by(PageRevision.created_at.desc(), PageRevision.id.desc())
        .offset(MAX_REVISIONS)
    )
    db.session.execute(delete(PageRevision).where(PageRevision.id.in_(old.scalar_subquery())))


def list_revisions(page: Page, page_no: int, limit: int) -> tuple[list[PageRevision], int]:
    query = select(PageRevision).where(PageRevision.page_id == page.id)
    total = db.session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = db.session.execute(
        query.order_by(PageRevision.created_at.desc(), PageRevision.id.desc())
        .offset((page_no - 1) * limit)
        .limit(limit)
    )
    return list(rows.scalars()), total


def get_revision(page: Page, revision_id: int) -> PageRevision:
    revision = db.session.get(PageRevision, revision_id)
    if revision is None or revision.page_id != page.id:
        raise not_found("Versione non trovata")
    return revision


def restore(actor: User, page: Page, revision_id: int, draft_version: int) -> int:
    """D-42: la revisione torna nella bozza (mai online). La bozza attuale non va persa."""
    revision = get_revision(page, revision_id)
    clean = validate_document(active_theme(), revision.snapshot_json, Mode.DRAFT)
    current = drafts.load(page.id)
    if current is not None and current.version == draft_version:
        add(page.id, RevisionKind.DRAFT, current.data_json, actor.id)
    version = drafts.write(actor, page, draft_version, clean, announce=False)
    audit.record(
        "page.revision_restored",
        actor_id=actor.id,
        entity="page",
        entity_id=page.id,
        diff={"revision_id": revision.id, "kind": revision.kind},
    )
    prune(page.id)
    db.session.commit()
    return version


def serialize(revision: PageRevision, *, with_snapshot: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": revision.id,
        "kind": revision.kind,
        "author_id": revision.author_id,
        "created_at": revision.created_at.isoformat(),
    }
    if with_snapshot:
        data["snapshot"] = revision.snapshot_json
    return data
