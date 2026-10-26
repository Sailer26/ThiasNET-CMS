"""Lingua del pannello (D-159): `?locale=` su ogni schermata, controllata sul tema."""

from __future__ import annotations

from flask import request

from app.services.errors import ServiceError
from app.services.theme import active_theme


def panel_locale() -> str:
    theme = active_theme()
    raw = request.args.get("locale")
    if not raw:
        return theme.locales[0]
    if raw not in theme.locales:
        raise ServiceError("unknown_locale", "Lingua non attiva in questo sito", 422)
    return raw
