"""Traduzioni collegate (D-151, D-158 … D-161).

Una traduzione nasce come copia della bozza dell'originale, nella lingua scelta, nello stesso
gruppo (`translation_group`): una sola per lingua. La pagina superiore è la traduzione della
pagina superiore (se c'è, altrimenti il primo livello); la homepage diventa la homepage di quella
lingua. Da lì ogni lingua è una pagina a sé (cestino compreso, D-161).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.extensions import db
from app.models.entry import Entry
from app.models.page import Page
from app.models.user import User
from app.services import audit, collections, drafts, entries, pages
from app.services.blocks import Mode
from app.services.content import validate_document
from app.services.errors import ServiceError
from app.services.page_paths import live, public_path
from app.services.page_views import is_home
from app.services.site_languages import label
from app.services.theme import Theme, active_theme


def _check_locale(theme: Theme, source: str, locale: str) -> None:
    if locale not in theme.locales:
        raise ServiceError("unknown_locale", "Lingua non attiva in questo sito", 422)
    if locale == source:
        raise ServiceError("same_locale", "È già in questa lingua: scegline un'altra", 422)


def _page_in(group: str, locale: str) -> Page | None:
    query = select(Page).where(live(), Page.translation_group == group, Page.locale == locale)
    return db.session.execute(query.limit(1)).scalar_one_or_none()


def translate_page(actor: User, page: Page, locale: str) -> Page:
    theme = active_theme()
    _check_locale(theme, page.locale, locale)
    if pages.translation_taken(page.translation_group, locale):
        raise pages.translation_exists()
    clean = validate_document(theme, drafts.view(page)["data"], Mode.DRAFT)
    parent_id: int | None = None
    if page.parent_id is not None:
        parent = db.session.get(Page, page.parent_id)
        found = _page_in(parent.translation_group, locale) if parent is not None else None
        parent_id = found.id if found is not None else None
    created = pages.create_page(
        actor,
        title=clean["title"] or page.title,
        layout=clean["layout"],
        locale=locale,
        parent_id=parent_id,
        slug="" if is_home(page) else None,
        translation_group=page.translation_group,
    )
    # create_page ha messo una bozza vuota (versione 1): ora la copia dell'originale.
    drafts.write(actor, created, 1, {**clean, "title": created.title}, announce=False)
    audit.record(
        "page.translated",
        actor_id=actor.id,
        entity="page",
        entity_id=created.id,
        diff={"from": page.id, "locale": locale},
    )
    db.session.commit()
    return created


def translate_entry(actor: User, entry: Entry, locale: str) -> Entry:
    theme = active_theme()
    _check_locale(theme, entry.locale, locale)
    if entries.translation_taken(entry.translation_group, locale):
        raise entries.translation_exists()
    clean = collections.validate(
        theme, entry.collection, entries.draft_view(entry)["data"], Mode.DRAFT
    )
    created = entries.create(
        actor,
        entry.collection,
        title=clean["title"] or entry.title,
        locale=locale,
        translation_group=entry.translation_group,
    )
    entries.store_draft(actor, created, 1, {**clean, "title": created.title})
    audit.record(
        "entry.translated",
        actor_id=actor.id,
        entity="entry",
        entity_id=created.id,
        diff={"from": entry.id, "locale": locale},
    )
    db.session.commit()
    return created


def page_translations(page: Page) -> list[dict[str, Any]]:
    theme = active_theme()
    query = select(Page).where(live(), Page.translation_group == page.translation_group)
    found = {row.locale: row for row in db.session.execute(query).scalars()}
    rows = []
    for locale in theme.locales:
        row = found.get(locale)
        rows.append(
            {
                "locale": locale,
                "label": label(locale),
                "id": row.id if row else None,
                "title": row.title if row else None,
                "status": row.status if row else None,
                "path": public_path(locale, row.path, theme) if row else None,
            }
        )
    return rows


def entry_translations(entry: Entry) -> list[dict[str, Any]]:
    theme = active_theme()
    query = select(Entry).where(
        Entry.deleted_at.is_(None), Entry.translation_group == entry.translation_group
    )
    found = {row.locale: row for row in db.session.execute(query).scalars()}
    rows = []
    for locale in theme.locales:
        row = found.get(locale)
        rows.append(
            {
                "locale": locale,
                "label": label(locale),
                "id": row.id if row else None,
                "title": row.title if row else None,
                "status": row.status if row else None,
                "url": entries.public_url(row, theme) if row else None,
            }
        )
    return rows
