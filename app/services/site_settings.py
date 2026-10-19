"""Impostazioni del sito e del tema viste dal rendering (D-57, D-143).

Dalla Fase 6 vengono dal pannello (tabella `settings`); la configurazione (`.env`) dà solo
i valori iniziali di nome e destinatario, e resta l'unica fonte per SITE_URL e Matomo.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from flask import current_app

from app.services.theme import Theme, active_theme

HEX_COLOR = frozenset("0123456789ABCDEF")


@dataclass(frozen=True)
class SiteSettings:
    name: str
    base_url: str
    contact_recipient: str | None
    matomo_url: str | None
    matomo_site_id: str | None
    logo: int | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    social: tuple[tuple[str, str], ...] = ()


def current() -> SiteSettings:
    from app.services import settings_store  # usa il database: import solo qui
    from app.services.settings_fields import SOCIAL_KEYS

    config = current_app.config
    values = settings_store.effective("site", active_theme())
    return SiteSettings(
        name=str(values.get("name") or config["SITE_NAME"]),
        base_url=str(config["SITE_URL"]),
        contact_recipient=values.get("contact_recipient") or None,
        matomo_url=config.get("MATOMO_URL") or None,
        matomo_site_id=config.get("MATOMO_SITE_ID") or None,
        logo=values.get("logo"),
        email=values.get("email"),
        phone=values.get("phone"),
        address=values.get("address"),
        social=tuple((key, values[key]) for key in SOCIAL_KEYS if values.get(key)),
    )


def theme_settings(theme: Theme) -> Mapping[str, Any]:
    from app.services import settings_store

    return MappingProxyType(settings_store.effective("appearance", theme))


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
