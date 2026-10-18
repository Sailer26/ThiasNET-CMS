"""Prepara i dati di una pagina per il renderer: documento, menu, percorso, impostazioni."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from flask import current_app

from app.models.page import Page
from app.services import drafts, public_pages, site_settings
from app.services.page_paths import HOME_PATH
from app.services.public_texts import text
from app.services.render import Renderer
from app.services.render_context import (
    Analytics,
    ContactFormView,
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


def site_info(locale: str) -> SiteInfo:
    settings = site_settings.current()
    return SiteInfo(
        name=settings.name,
        base_url=settings.base_url,
        locale=active_theme().locales[0],
        year=datetime.now(UTC).year,
    )


def _analytics() -> Analytics | None:
    settings = site_settings.current()
    if settings.matomo_url and settings.matomo_site_id:
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


def page_context(
    page: Page,
    *,
    mode: RenderMode = RenderMode.PUBLIC,
    document: Mapping[str, Any] | None = None,
    forms: Mapping[str, ContactFormView] | None = None,
) -> PageContext:
    theme = active_theme()
    values, css_version = theme_values(theme)
    return PageContext(
        page=page_view(page, document),
        site=site_info(page.locale),
        mode=mode,
        menu=public_pages.auto_menu(page.locale, page, theme),
        breadcrumbs=public_pages.breadcrumbs(page, theme),
        settings=values,
        css_version=css_version,
        analytics=_analytics(),
        forms=MappingProxyType(dict(forms or {})),
    )


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
    return PageContext(
        page=view,
        site=site_info(locale),
        menu=public_pages.auto_menu(locale, None, theme),
        settings=values,
        css_version=css_version,
        analytics=_analytics(),
    )
