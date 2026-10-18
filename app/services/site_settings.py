"""Impostazioni del sito e del tema viste dal rendering (D-57).

Fino alla Fase 6 le impostazioni del sito vengono dalla configurazione (`.env`, impostate da
Thias al deploy) e quelle del tema sono i `default` di `theme.json`. Dalla Fase 6 queste due
funzioni leggeranno dal database: chi le usa non cambia.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from flask import current_app

from app.services.theme import Theme

HEX_COLOR = frozenset("0123456789ABCDEF")


@dataclass(frozen=True)
class SiteSettings:
    name: str
    base_url: str
    contact_recipient: str | None
    matomo_url: str | None
    matomo_site_id: str | None


def current() -> SiteSettings:
    config = current_app.config
    return SiteSettings(
        name=str(config["SITE_NAME"]),
        base_url=str(config["SITE_URL"]),
        contact_recipient=config.get("CONTACT_RECIPIENT") or None,
        matomo_url=config.get("MATOMO_URL") or None,
        matomo_site_id=config.get("MATOMO_SITE_ID") or None,
    )


def theme_settings(theme: Theme) -> Mapping[str, Any]:
    return MappingProxyType({key: spec.default for key, spec in theme.settings.items()})


def _is_hex_color(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 7
        and value.startswith("#")
        and set(value[1:].upper()) <= HEX_COLOR
    )


def css_variables(theme: Theme, values: Mapping[str, Any]) -> str:
    """D-59: solo colori validati (hex, nella palette se dichiarata) come variabili CSS."""
    lines = []
    for key, spec in sorted(theme.settings.items()):
        value = values.get(key)
        if spec.type != "color" or not _is_hex_color(value):
            continue
        color = str(value).upper()
        if spec.palette and color not in spec.palette:
            continue
        lines.append(f"  --{key.replace('_', '-')}: {color};")
    return ":root {\n" + "\n".join(lines) + "\n}\n"


def css_version(css: str) -> str:
    return hashlib.sha256(css.encode("utf-8")).hexdigest()[:12]
