"""Le lingue sul sito (D-151, D-158): selettore, hreflang e sitemap.

Una lingua compare solo quando la sua homepage è online (la prima lingua del tema sempre);
con una sola lingua visibile il selettore non c'è. Senza traduzione di questa pagina, il
selettore porta alla homepage di quella lingua e la lingua resta fuori dagli hreflang.
"""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import select

from app.extensions import db
from app.models.entry import Entry, EntryStatus
from app.models.page import Page, PageStatus
from app.services import entries
from app.services.page_paths import HOME_PATH, live, public_path
from app.services.render_context import Language
from app.services.theme import Theme

LANGUAGE_NAMES = {"it": "Italiano", "de": "Deutsch", "rm": "Rumantsch", "en": "English"}


def label(locale: str) -> str:
    return LANGUAGE_NAMES.get(locale, locale)


def visible_locales(theme: Theme) -> tuple[str, ...]:
    query = select(Page.locale).where(
        live(), Page.status == PageStatus.PUBLISHED, Page.path == HOME_PATH
    )
    with_home = set(db.session.execute(query).scalars())
    first, *others = theme.locales
    return (first, *(locale for locale in others if locale in with_home))


def _build(theme: Theme, current: str, found: Mapping[str, str]) -> tuple[Language, ...]:
    visible = visible_locales(theme)
    if len(visible) < 2:
        return ()
    return tuple(
        Language(
            locale=locale,
            label=label(locale),
            url=found.get(locale) or public_path(locale, HOME_PATH, theme),
            current=locale == current,
            translated=locale in found,
        )
        for locale in visible
    )


def for_page(page: Page, theme: Theme) -> tuple[Language, ...]:
    query = select(Page.locale, Page.path).where(
        live(),
        Page.status == PageStatus.PUBLISHED,
        Page.translation_group == page.translation_group,
    )
    found = {locale: public_path(locale, path, theme) for locale, path in db.session.execute(query)}
    found[page.locale] = public_path(page.locale, page.path, theme)  # anche in anteprima
    return _build(theme, page.locale, found)


def for_entry(entry: Entry, url: str, theme: Theme) -> tuple[Language, ...]:
    query = select(Entry.collection, Entry.locale, Entry.slug).where(
        Entry.deleted_at.is_(None),
        Entry.status == EntryStatus.PUBLISHED,
        Entry.translation_group == entry.translation_group,
    )
    found: dict[str, str] = {}
    for collection, locale, slug in db.session.execute(query):
        listing = entries.listing_page(theme, collection, locale, online=True)
        if listing is not None:
            found[locale] = entries.entry_url(listing, slug, theme)
    found[entry.locale] = url
    return _build(theme, entry.locale, found)
