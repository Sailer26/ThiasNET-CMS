"""Letture delle pagine per il pannello: elenco, albero, cestino e serializzazione."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from app.extensions import db
from app.models.page import Page, PageDraft
from app.services.authors import display_name
from app.services.page_paths import live

TREE_LIMIT = 2000


def is_home(page: Page) -> bool:
    return page.slug == ""


def draft_ids(page_ids: Sequence[int]) -> set[int]:
    if not page_ids:
        return set()
    query = select(PageDraft.page_id).where(PageDraft.page_id.in_(page_ids))
    return set(db.session.execute(query).scalars())


def list_pages(
    *,
    locale: str | None,
    parent_id: int | None,
    status: str | None,
    q: str | None,
    page_no: int,
    limit: int,
) -> tuple[list[Page], int]:
    """Ricerca nel titolo: su SQLite non distingue maiuscole solo per le lettere ASCII."""
    query = select(Page).where(live())
    if locale:
        query = query.where(Page.locale == locale)
    if parent_id is not None:
        query = query.where(Page.parent_id == parent_id)
    if status:
        query = query.where(Page.status == status)
    if q:
        query = query.where(Page.title.icontains(q, autoescape=True))
    total = db.session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = db.session.execute(
        query.order_by(Page.path, Page.id).offset((page_no - 1) * limit).limit(limit)
    )
    return list(rows.scalars()), total


def tree(locale: str) -> tuple[list[dict[str, Any]], bool]:
    """Albero di una lingua (tetto TREE_LIMIT) con la homepage per prima, e se è troncato."""
    query = select(Page).where(live(), Page.locale == locale).order_by(Page.sort, Page.id)
    pages = list(db.session.execute(query.limit(TREE_LIMIT + 1)).scalars())
    truncated = len(pages) > TREE_LIMIT
    pages = pages[:TREE_LIMIT]
    with_draft = draft_ids([p.id for p in pages])
    nodes = {p.id: {**serialize(p, has_draft=p.id in with_draft), "children": []} for p in pages}
    roots: list[dict[str, Any]] = []
    for page in pages:
        parent = nodes.get(page.parent_id) if page.parent_id is not None else None
        (parent["children"] if parent is not None else roots).append(nodes[page.id])
    return sorted(roots, key=lambda node: not node["is_home"]), truncated


def list_trash(page_no: int, limit: int) -> tuple[list[Page], int]:
    query = select(Page).where(Page.deleted_at.is_not(None))
    total = db.session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = db.session.execute(
        query.order_by(Page.deleted_at.desc(), Page.id).offset((page_no - 1) * limit).limit(limit)
    )
    return list(rows.scalars()), total


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def serialize(page: Page, *, has_draft: bool) -> dict[str, Any]:
    return {
        "id": page.id,
        "parent_id": page.parent_id,
        "locale": page.locale,
        "translation_group": page.translation_group,
        "slug": page.slug,
        "path": page.path,
        "is_home": is_home(page),
        "title": page.title,
        "layout": page.layout,
        "status": page.status,
        "publish_at": _iso(page.publish_at),
        "published_at": _iso(page.published_at),
        "seo": page.seo_json,
        "sort": page.sort,
        "version": page.version,
        "has_draft": has_draft,
        "created_at": _iso(page.created_at),
        "updated_at": _iso(page.updated_at),
        "updated_by": page.updated_by,
        "deleted_at": _iso(page.deleted_at),
    }


def _schedule(page: Page) -> dict[str, Any] | None:
    """La programmazione in attesa: le modifiche successive alla bozza non ci entrano (D-122)."""
    from app.services import drafts, revisions  # evita il ciclo con revisions → page_views

    pending = revisions.pending_schedule(page.id)
    if pending is None or page.publish_at is None:
        return None
    draft = drafts.load(page.id)
    return {
        "publish_at": _iso(page.publish_at),
        "revision_id": pending.id,
        "author_name": display_name(pending.author_id),
        "draft_newer": draft is not None and draft.updated_at > pending.created_at,
    }


def serialize_one(page: Page) -> dict[str, Any]:
    return {**serialize(page, has_draft=bool(draft_ids([page.id]))), "schedule": _schedule(page)}


def serialize_many(pages: Sequence[Page]) -> list[dict[str, Any]]:
    with_draft = draft_ids([p.id for p in pages])
    return [serialize(p, has_draft=p.id in with_draft) for p in pages]
