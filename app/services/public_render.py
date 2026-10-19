"""Prepara i dati di una pagina per il renderer: documento, menu, percorso, impostazioni."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from flask import current_app

from app.models.page import Page
from app.services import drafts, media_library, media_refs, public_pages, site_settings
from app.services.blocks import get_registry
from app.services.page_paths import HOME_PATH
from app.services.public_texts import text
from app.services.render import Renderer
from app.services.render_context import (
    Analytics,
    ContactFormView,
    MediaView,
    PageContext,
    PageView,
    RenderMode,
    SiteInfo,
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


def page_context(
    page: Page,
    *,
    mode: RenderMode = RenderMode.PUBLIC,
    document: Mapping[str, Any] | None = None,
    forms: Mapping[str, ContactFormView] | None = None,
    view: PageView | None = None,
) -> PageContext:
    """`view` già pronta evita di normalizzare due volte lo stesso documento."""
    theme = active_theme()
    values, css_version = theme_values(theme)
    page_view_ = view if view is not None else page_view(page, document)
    site = site_info()
    media, og_image = page_media(page_view_, (site.logo,))
    return PageContext(
        page=page_view_,
        media=media,
        og_image=og_image,
        site=site,
        mode=mode,
        menu=public_pages.auto_menu(page.locale, page, theme),
        breadcrumbs=public_pages.breadcrumbs(page, theme),
        settings=values,
        css_version=css_version,
        analytics=_analytics(),
        forms=MappingProxyType(dict(forms or {})),
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
        menu=public_pages.auto_menu(locale, None, theme),
        settings=values,
        css_version=css_version,
        analytics=_analytics(),
    )
