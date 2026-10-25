"""Dati del sito per il pannello: nome, indirizzo, lingue (D-94), layout di partenza (D-95)."""

from __future__ import annotations

from collections.abc import Mapping

from flask import Response

from app.api import ok
from app.api.admin import bp
from app.api.admin.decorators import require_permission
from app.services import site_settings
from app.services.permissions import Permission
from app.services.theme import active_theme

PAGE_LAYOUT, HOME_LAYOUT = "page", "home"


def _layout(layouts: Mapping[str, object], preferred: str) -> str:
    return preferred if preferred in layouts else next(iter(layouts))


@bp.get("/site")
@require_permission(Permission.PROFILE)
def site_info() -> Response:
    theme, site = active_theme(), site_settings.current()
    locales = list(theme.locales)
    return ok(
        {
            "name": site.name,
            "url": site.base_url,
            "locales": locales,
            "default_locale": locales[0],
            # D-95: una pagina nuova nasce come "page" (o col primo layout), la homepage come
            # "home"; il layout si cambia poi nell'editor.
            "default_layout": _layout(theme.layouts, PAGE_LAYOUT),
            "home_layout": _layout(theme.layouts, HOME_LAYOUT),
            # Fase 7b: una voce del menu del pannello per raccolta (le notizie, D-148).
            "collections": [{"key": k, "label": c.label} for k, c in theme.collections.items()],
        }
    )
