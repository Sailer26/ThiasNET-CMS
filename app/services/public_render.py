"""Prepara i dati di una pagina per il renderer: documento, menu, percorso, impostazioni."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from flask import current_app
from sqlalchemy import Select, func, select

from app.extensions import db
from app.models.entry import Entry, EntryStatus
from app.models.page import Page
from app.services import (
    collections,
    drafts,
    entries,
    media_library,
    media_refs,
    menus,
    public_pages,
    site_languages,
    site_settings,
    widgets,
)
from app.services.blocks import get_registry
from app.services.page_paths import HOME_PATH
from app.services.public_texts import text
from app.services.render import Renderer
from app.services.render_context import (
    Analytics,
    ContactFormView,
    EntryView,
    Link,
    ListingView,
    MediaView,
    PageContext,
    PageView,
    RenderMode,
    SiteInfo,
    WidgetView,
    normalize_document,
)
from app.services.theme import Theme, active_theme

RENDERER_KEY = "thiasnet.renderer"


def renderer() -> Renderer:
    """Un renderer per il tema attivo (template compilati e hash degli asset in memoria)."""
    theme = active_theme()
    current = current_app.extensions.get(RENDERER_KEY)
    if not isinstance(current, Renderer) or current.theme is not theme:
        strict = bool(current_app.debug or current_app.testing)
        current = Renderer(theme, strict=strict)
        current_app.extensions[RENDERER_KEY] = current
    return current


def site_info() -> SiteInfo:
    settings = site_settings.current()
    return SiteInfo(
        name=settings.name,
        base_url=settings.base_url,
        locale=active_theme().locales[0],
        year=datetime.now(UTC).year,
        logo=settings.logo,
        email=settings.email,
        phone=settings.phone,
        address=settings.address,
        social=settings.social,
    )


def _analytics() -> Analytics | None:
    settings = site_settings.current()
    if settings.matomo_url and settings.matomo_site_id:  # D-66
        return Analytics(url=settings.matomo_url, site_id=settings.matomo_site_id)
    return None


def theme_values(theme: Theme) -> tuple[Mapping[str, Any], str]:
    values = site_settings.theme_settings(theme)
    css = site_settings.css_variables(theme, values)
    return values, site_settings.css_version(css)


def page_view(page: Page, document: Mapping[str, Any] | None = None) -> PageView:
    theme = active_theme()
    source = document if document is not None else drafts.published_document(page)
    return normalize_document(
        theme,
        source,
        page_id=page.id,
        locale=page.locale,
        path=public_pages.public_url(page, theme),
        is_home=page.path == HOME_PATH,
    )


def _view_refs(view: PageView) -> list[int]:
    registry = get_registry()
    ids = [
        ref.media_id
        for blocks in view.zones.values()
        for block in blocks
        for ref in registry.media_refs(block.type, block.data)
    ]
    og = view.seo.get("og_image_media_id")
    return [og, *ids] if isinstance(og, int) and not isinstance(og, bool) else ids


def page_media(
    view: PageView, extra: tuple[int | None, ...] = ()
) -> tuple[Mapping[int, MediaView], MediaView | None]:
    """Media usati dalla pagina (una query) e immagine per i social: quella della SEO,
    altrimenti la prima immagine della pagina (D-81). `extra`: il logo del sito."""
    refs = _view_refs(view)
    wanted = [*refs, *(mid for mid in extra if mid is not None)]
    found = {mid: media_library.to_view(m) for mid, m in media_refs.load(wanted).items()}
    og = next((found[mid] for mid in refs if mid in found and found[mid].kind == "image"), None)
    return MappingProxyType(found), og


# --- Raccolte (D-147, D-149) -----------------------------------------------------------


def _online_entries(collection: str, locale: str) -> Select[Entry]:
    return select(Entry).where(
        Entry.deleted_at.is_(None),
        Entry.collection == collection,
        Entry.locale == locale,
        Entry.status == EntryStatus.PUBLISHED,
    )


def listing_pages(page: Page, theme: Theme) -> int | None:
    """Quante pagine ha l'elenco (almeno una); None se la pagina non elenca una raccolta."""
    collection = public_pages.listing_collection(page, theme)
    spec = None if collection is None else theme.collections.get(collection)
    if collection is None or spec is None:
        return None
    count = select(func.count()).select_from(_online_entries(collection, page.locale).subquery())
    total = int(db.session.execute(count).scalar_one())
    return max(1, -(-total // spec.per_page))


def entry_view(entry: Entry, listing: Page, theme: Theme) -> EntryView:
    fields = collections.lenient(theme, entry.collection, entry.fields_json or {})
    return EntryView(
        id=entry.id,
        collection=entry.collection,
        title=entry.title,
        url=entries.entry_url(listing, entry.slug, theme),
        fields=MappingProxyType(fields),
        published_at=None if entry.published_at is None else entry.published_at.isoformat(),
    )


def _entry_media(views: tuple[EntryView, ...], theme: Theme) -> list[int]:
    return [
        ref.media_id
        for view in views
        for ref in collections.media_refs(theme, view.collection, {"fields": view.fields})
    ]


LATEST_DEFAULT = 3  # D-155


def _latest(view: WidgetView, locale: str, theme: Theme) -> WidgetView:
    """Il widget "ultime notizie": le voci online più recenti, sotto la pagina elenco online.
    Senza pagina elenco resta vuoto (il template non mostra nulla)."""
    wanted = view.data.get("collection")
    collection = wanted if isinstance(wanted, str) else next(iter(theme.collections), None)
    if collection is None or collection not in theme.collections:
        return view
    listing = entries.listing_page(theme, collection, locale, online=True)
    if listing is None:
        return view
    limit = view.data.get("limit")
    count = limit if isinstance(limit, int) and not isinstance(limit, bool) else LATEST_DEFAULT
    query = (
        _online_entries(collection, locale)
        .order_by(Entry.sort_at.desc(), Entry.published_at.desc(), Entry.id.desc())
        .limit(max(1, min(count, 10)))
    )
    found = tuple(entry_view(e, listing, theme) for e in db.session.execute(query).scalars())
    return replace(view, entries=found)


def with_latest_entries(
    areas: Mapping[str, tuple[WidgetView, ...]], locale: str, theme: Theme
) -> Mapping[str, tuple[WidgetView, ...]]:
    """Le notizie nella lingua della pagina, come i widget della sua area."""
    return MappingProxyType(
        {
            name: tuple(
                _latest(view, locale, theme) if view.type == "latest_entries" else view
                for view in views
            )
            for name, views in areas.items()
        }
    )


def listing_view(page: Page, theme: Theme, number: int) -> ListingView | None:
    """Le voci online della pagina `number` dell'elenco, dalla più recente (D-149)."""
    collection = public_pages.listing_collection(page, theme)
    spec = None if collection is None else theme.collections.get(collection)
    pages = listing_pages(page, theme)
    if collection is None or spec is None or pages is None:
        return None
    query = (
        _online_entries(collection, page.locale)
        .order_by(Entry.sort_at.desc(), Entry.published_at.desc(), Entry.id.desc())
        .offset((number - 1) * spec.per_page)
        .limit(spec.per_page)
    )
    items = tuple(entry_view(e, page, theme) for e in db.session.execute(query).scalars())
    base = public_pages.public_url(page, theme)
    prev_url = None if number <= 1 else (base if number == 2 else f"{base}?p={number - 1}")
    next_url = f"{base}?p={number + 1}" if number < pages else None
    return ListingView(collection, items, number, pages, prev_url, next_url)


def page_context(
    page: Page,
    *,
    mode: RenderMode = RenderMode.PUBLIC,
    document: Mapping[str, Any] | None = None,
    forms: Mapping[str, ContactFormView] | None = None,
    view: PageView | None = None,
    listing_number: int = 1,
) -> PageContext:
    """`view` già pronta evita di normalizzare due volte lo stesso documento. Una pagina
    elenco porta con sé le voci della pagina `listing_number`."""
    theme = active_theme()
    values, css_version = theme_values(theme)
    page_view_ = view if view is not None else page_view(page, document)
    listing = listing_view(page, theme, listing_number)
    if listing is not None and listing_number > 1:  # canonical con il numero di pagina
        page_view_ = replace(page_view_, path=f"{page_view_.path}?p={listing_number}")
    site = site_info()
    extra = (site.logo, *(_entry_media(listing.items, theme) if listing else ()))
    media, og_image = page_media(page_view_, extra)
    return PageContext(
        listing=listing,
        page=page_view_,
        media=media,
        og_image=og_image,
        site=site,
        mode=mode,
        menus=menus.site_menus(page.locale, page, theme),
        widgets=with_latest_entries(
            widgets.site_widgets(page.locale, page.id, theme), page.locale, theme
        ),
        languages=site_languages.for_page(page, theme),
        breadcrumbs=public_pages.breadcrumbs(page, theme),
        settings=values,
        css_version=css_version,
        analytics=_analytics(),
        forms=MappingProxyType(dict(forms or {})),
    )


def entry_context(
    listing: Page,
    entry: Entry,
    *,
    document: Mapping[str, Any] | None = None,
    mode: RenderMode = RenderMode.PUBLIC,
) -> PageContext:
    """Il dettaglio di una voce: menu, widget e briciole della sua pagina elenco (D-149).
    Con `document` (anteprima, D-156) si mostra quello al posto della versione pubblicata."""
    theme = active_theme()
    values, css_version = theme_values(theme)
    view = entry_view(entry, listing, theme)
    seo = dict(entry.seo_json or {})
    if document is not None:
        fields = collections.lenient(theme, entry.collection, document.get("fields") or {})
        view = replace(
            view, title=str(document.get("title") or entry.title), fields=MappingProxyType(fields)
        )
        seo = dict(document.get("seo") or {})
    page = PageView(
        id=None,
        locale=entry.locale,
        title=view.title,
        layout=listing.layout,
        path=view.url,
        seo=MappingProxyType(seo),
        zones=MappingProxyType({}),
        is_home=False,
    )
    site = site_info()
    document = {"fields": view.fields, "seo": page.seo}
    refs = collections.media_refs(theme, entry.collection, document)
    media, _og = page_media(page, (site.logo, *(ref.media_id for ref in refs)))
    images = (media.get(ref.media_id) for ref in refs)
    og = next((m for m in images if m is not None and m.kind == "image"), None)
    crumbs = tuple(
        replace(link, current=False) for link in public_pages.breadcrumbs(listing, theme)
    )
    return PageContext(
        page=page,
        media=media,
        og_image=og,
        site=site,
        mode=mode,
        menus=menus.site_menus(entry.locale, listing, theme),
        widgets=with_latest_entries(
            widgets.site_widgets(entry.locale, listing.id, theme), entry.locale, theme
        ),
        languages=site_languages.for_entry(entry, view.url, theme),
        breadcrumbs=(*crumbs, Link(view.title, view.url, current=True)),
        settings=values,
        css_version=css_version,
        analytics=_analytics(),
        entry=view,
    )


def cacheable(context: PageContext) -> bool:
    """Le pagine con modulo contatti hanno un token fresco a ogni visita (D-61)."""
    return context.mode is RenderMode.PUBLIC and not context.forms


def not_found_context(locale: str, path: str) -> PageContext:
    theme = active_theme()
    values, css_version = theme_values(theme)
    view = PageView(
        id=None,
        locale=locale,
        title=text("not_found_title", locale),
        layout="404",
        path=path,
        seo=MappingProxyType({"noindex": True}),
        zones=MappingProxyType({}),
        is_home=False,
    )
    site = site_info()
    media, _og = page_media(view, (site.logo,))
    return PageContext(
        page=view,
        media=media,
        site=site,
        menus=menus.site_menus(locale, None, theme),
        widgets=with_latest_entries(widgets.site_widgets(locale, None, theme), locale, theme),
        settings=values,
        css_version=css_version,
        analytics=_analytics(),
    )
