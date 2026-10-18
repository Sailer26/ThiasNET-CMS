"""Pagine d'errore del sito (D-65): 404 disegnata dal tema, 500 fissa del CMS."""

from __future__ import annotations

import logging

from flask import Response, current_app, request
from werkzeug.exceptions import HTTPException

from app.extensions import db
from app.public.responses import html_page
from app.services import public_render
from app.services.theme import active_theme

log = logging.getLogger("thiasnet.public")

# Nessun template: deve funzionare anche se il tema o il database sono rotti.
SERVER_ERROR_PAGE = (
    '<!doctype html><html lang="it"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">'
    "<title>Errore temporaneo</title></head><body>"
    "<h1>Si è verificato un errore</h1>"
    "<p>Riprova tra qualche minuto. Se il problema continua, contatta chi gestisce il sito.</p>"
    "</body></html>"
)
NOT_FOUND_FALLBACK = (
    '<!doctype html><html lang="it"><head><meta charset="utf-8"><title>Pagina non trovata</title>'
    '<meta name="robots" content="noindex"></head><body><h1>Pagina non trovata</h1>'
    '<p><a href="/">Torna alla pagina iniziale</a></p></body></html>'
)


def _locale_from_path() -> str:
    theme = active_theme()
    first = request.path.split("/")[1] if request.path.count("/") else ""
    return first if first in theme.locales else theme.locales[0]


def not_found_response(locale: str | None = None) -> Response:
    try:
        context = public_render.not_found_context(locale or _locale_from_path(), request.path)
        html = public_render.renderer().render_not_found(context)
    except Exception:  # il 404 non deve mai diventare un 500
        if current_app.testing:
            raise
        db.session.rollback()  # la sessione potrebbe essere rimasta in errore
        log.exception("404 del tema non disponibile")
        html = NOT_FOUND_FALLBACK
    return html_page(html, 404)


def html_error(exc: HTTPException) -> Response:
    status = exc.code or 500
    if status == 404:
        return not_found_response()
    if status >= 500:
        return html_page(SERVER_ERROR_PAGE, status)
    response = Response(exc.description or exc.name, status=status, mimetype="text/plain")
    for name, value in exc.get_headers():  # es. Allow sui 405
        if name.lower() != "content-type":
            response.headers[name] = value
    return response
