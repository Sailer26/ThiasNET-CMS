"""Catalogo dei blocchi per il pannello: schemi, layout e zone del tema, varianti (D-03)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import Response

from app.api import ok
from app.api.admin import bp
from app.api.admin.decorators import require_permission
from app.services.blocks import get_registry
from app.services.permissions import Permission
from app.services.theme import Theme, active_theme


def _plain(value: Any) -> Any:
    """Gli schemi del registry sono di sola lettura: copia serializzabile in JSON."""
    if isinstance(value, Mapping):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, tuple | list):
        return [_plain(v) for v in value]
    return value


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
    return {
        block: {
            "default": variants.default,
            "options": {
                key: {"label": option.label, "thumbnail": option.thumbnail}
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
            "schema": _plain(registry.schema(name)),
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
