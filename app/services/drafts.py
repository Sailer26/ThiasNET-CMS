"""Bozze (D-07, D-38, D-44): la copia di lavoro di una pagina, un documento JSON unico.

- Senza bozza si lavora sulla versione pubblicata, con `version` 0.
- Ogni scrittura manda la `version` conosciuta: se nel frattempo è cambiata → 409.
- L'autosave non tocca mai `pages`/`blocks` e non crea revisioni (D-40).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.page import Block, Page, PageDraft
from app.models.types import utcnow
from app.models.user import User
from app.services import audit
from app.services.blocks import Mode
from app.services.content import validate_document
from app.services.errors import ServiceError, not_found, version_conflict
from app.services.sql import rows_affected
from app.services.theme import active_theme

BLOCK_NOT_FOUND = "Blocco non trovato"
Document = dict[str, Any]


def load(page_id: int) -> PageDraft | None:
    return db.session.get(PageDraft, page_id)


def published_document(page: Page) -> Document:
    """La versione pubblicata nella stessa forma della bozza (zone del layout sempre presenti)."""
    theme = active_theme()
    zones: dict[str, list[dict[str, Any]]] = (
        {zone: [] for zone in theme.zones(page.layout)} if page.layout in theme.layouts else {}
    )
    query = select(Block).where(Block.page_id == page.id).order_by(Block.zone, Block.sort, Block.id)
    for block in db.session.execute(query).scalars():
        zones.setdefault(block.zone, []).append(
            {
                "uid": block.uid,
                "type": block.type,
                "variant": block.variant,
                "data": block.data_json,
            }
        )
    return {"title": page.title, "layout": page.layout, "seo": dict(page.seo_json), "zones": zones}


def view(page: Page) -> dict[str, Any]:
    draft = load(page.id)
    if draft is None:
        return {
            "version": 0,
            "data": published_document(page),
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


def conflict(draft: PageDraft | None) -> ServiceError:
    if draft is None:
        return version_conflict(0, None, None)
    return version_conflict(draft.version, draft.author_id, draft.updated_at)


def write(
    actor: User, page: Page, expected: int, document: Document, *, announce: bool = True
) -> int:
    """Salva un documento già validato e restituisce la nuova versione. Non fa commit."""
    draft = load(page.id)
    if expected == 0:
        if draft is not None:
            raise conflict(draft)
        db.session.add(
            PageDraft(page_id=page.id, data_json=document, version=1, author_id=actor.id)
        )
        if announce:  # D-41: dell'autosave si registra solo la nascita della bozza
            audit.record("page.draft_started", actor_id=actor.id, entity="page", entity_id=page.id)
        try:
            db.session.flush()
        except IntegrityError as exc:  # un'altra richiesta l'ha appena creata
            db.session.rollback()
            raise conflict(load(page.id)) from exc
        return 1
    if draft is None or draft.version != expected:
        raise conflict(draft)
    statement = (
        update(PageDraft)
        .where(PageDraft.page_id == page.id, PageDraft.version == expected)
        .values(data_json=document, version=expected + 1, author_id=actor.id, updated_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    if rows_affected(statement) != 1:
        db.session.rollback()
        raise conflict(load(page.id))
    db.session.expire(draft)
    return expected + 1


def store_draft(actor: User, page: Page, expected: int, document: Any) -> int:
    clean = validate_document(active_theme(), document, Mode.DRAFT)
    version = write(actor, page, expected, clean)
    db.session.commit()
    return version


def discard(actor: User, page: Page, expected: int) -> None:
    """Butta la bozza: si torna alla versione pubblicata (o alla pagina vuota)."""
    draft = load(page.id)
    if draft is None:
        raise ServiceError("no_draft", "Non ci sono modifiche da annullare", 409)
    if draft.version != expected:
        raise conflict(draft)
    statement = delete(PageDraft).where(PageDraft.page_id == page.id, PageDraft.version == expected)
    if rows_affected(statement) != 1:
        db.session.rollback()
        raise conflict(load(page.id))
    audit.record("page.draft_discarded", actor_id=actor.id, entity="page", entity_id=page.id)
    db.session.commit()


# --- Singoli blocchi -----------------------------------------------------------------


def _working(page: Page, expected: int) -> Document:
    """Copia indipendente del documento corrente, se la versione è quella attesa."""
    draft = load(page.id)
    current = 0 if draft is None else draft.version
    if current != expected:
        raise conflict(draft)
    # Nessuna copia: chi modifica costruisce sempre dizionari nuovi (_with_zone, {**block}).
    return draft.data_json if draft is not None else published_document(page)


def _find(document: Document, uid: str) -> tuple[str, int]:
    for zone, blocks in document["zones"].items():
        for index, block in enumerate(blocks):
            if block.get("uid") == uid:
                return zone, index
    raise not_found(BLOCK_NOT_FOUND)


def _commit_with_block(
    actor: User, page: Page, expected: int, document: Document, uid: str
) -> tuple[int, dict[str, Any]]:
    clean = validate_document(active_theme(), document, Mode.DRAFT)
    version = write(actor, page, expected, clean)
    db.session.commit()
    zone, index = _find(clean, uid)
    return version, clean["zones"][zone][index]


def _with_zone(document: Document, zone: str, blocks: list[dict[str, Any]]) -> Document:
    return {**document, "zones": {**document["zones"], zone: blocks}}


def add_block(
    actor: User,
    page: Page,
    expected: int,
    *,
    zone: str,
    block_type: str,
    data: Any,
    variant: str | None = None,
    position: int | None = None,
) -> tuple[int, dict[str, Any]]:
    document = _working(page, expected)
    block = {"uid": uuid.uuid4().hex, "type": block_type, "variant": variant, "data": data}
    blocks = list(document["zones"].get(zone, []))
    index = len(blocks) if position is None else max(0, min(position, len(blocks)))
    updated = _with_zone(document, zone, [*blocks[:index], block, *blocks[index:]])
    return _commit_with_block(actor, page, expected, updated, block["uid"])


def update_block(
    actor: User, page: Page, expected: int, uid: str, changes: Mapping[str, Any]
) -> tuple[int, dict[str, Any]]:
    document = _working(page, expected)
    zone, index = _find(document, uid)
    blocks = document["zones"][zone]
    changed = {**blocks[index], **{k: changes[k] for k in ("variant", "data") if k in changes}}
    updated = _with_zone(document, zone, [*blocks[:index], changed, *blocks[index + 1 :]])
    return _commit_with_block(actor, page, expected, updated, uid)


def delete_block(actor: User, page: Page, expected: int, uid: str) -> int:
    document = _working(page, expected)
    zone, index = _find(document, uid)
    blocks = document["zones"][zone]
    return store_draft(
        actor, page, expected, _with_zone(document, zone, [*blocks[:index], *blocks[index + 1 :]])
    )


def reorder_blocks(
    actor: User, page: Page, expected: int, order: Mapping[str, Sequence[str]]
) -> int:
    """Nuovo ordine (anche tra zone diverse): va elencato ogni blocco, una volta sola."""
    document = _working(page, expected)
    by_uid = {b.get("uid"): b for blocks in document["zones"].values() for b in blocks}
    listed = [uid for uids in order.values() for uid in uids]
    if len(listed) != len(set(listed)) or set(listed) != set(by_uid):
        raise ServiceError(
            "reorder_mismatch",
            "L'elenco dei blocchi non corrisponde alla pagina: ricarica e riprova",
            422,
        )
    zones = {zone: [] for zone in document["zones"]} | {
        zone: [by_uid[uid] for uid in uids] for zone, uids in order.items()
    }
    return store_draft(actor, page, expected, {**document, "zones": zones})
