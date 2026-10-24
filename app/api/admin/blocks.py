"""Catalogo dei blocchi per il pannello: schemi, layout e zone del tema, varianti (D-03)."""

from __future__ import annotations

from typing import Any

from flask import Response

from app.api import ok
from app.api.admin import bp
from app.api.admin.decorators import require_permission
from app.services.blocks import get_registry, plain
from app.services.permissions import Permission
from app.services.public_render import renderer
from app.services.theme import Theme, active_theme


def _layouts(theme: Theme) -> dict[str, Any]:
    return {
        name: {
            "label": layout.label,
            "zones": {
                zone.name: {"label": zone.label, "blocks": list(zone.blocks), "max": zone.max}
                for zone in layout.zones.values()
            },
        }
        for name, layout in theme.layouts.items()
    }


def _variants(theme: Theme) -> dict[str, Any]:
    assets = renderer()  # miniature con la versione nel nome: cache lunga, sempre aggiornate
    return {
        block: {
            "default": variants.default,
            "options": {
                key: {
                    "label": option.label,
                    "thumbnail": option.thumbnail,
                    "thumbnail_url": assets.asset_url(option.thumbnail),
                }
                for key, option in variants.options.items()
            },
        }
        for block, variants in theme.block_variants.items()
    }


@bp.get("/blocks")
@require_permission(Permission.CONTENT_EDIT)
def blocks_catalog() -> Response:
    registry, theme = get_registry(), active_theme()
    types = {
        name: {
            "label": registry.schema(name).get("title", name),
            "schema": plain(registry.schema(name)),
        }
        for name in sorted(registry.types)
    }
    return ok(
        {
            "types": types,
            "layouts": _layouts(theme),
            "variants": _variants(theme),
            "locales": list(theme.locales),
        }
    )
