"""Sito pubblico: pagine, asset del tema, anteprima e modulo contatti (Fase 3).

Route sottili: la logica sta in `app/services/` (public_pages, public_render, render, ...).
"""

from __future__ import annotations

from flask import Blueprint, Flask

bp = Blueprint("public", __name__)


def register_public(app: Flask) -> None:
    from app.public import contact, media, preview, responses, routes  # noqa: F401  (route registrate all'import)

    app.register_blueprint(bp)
    responses.register(app)
