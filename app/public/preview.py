"""Anteprima nel pannello (D-55): GET mostra la bozza salvata, POST quella in corso.

Solo chi ha `content.edit`; agli altri un 404 (la pagina "non esiste"). Solo qui la pagina può
stare in un iframe dello stesso sito. Nessuna scrittura: né bozza, né revisioni, né cache.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import Response, request
from flask_login import current_user
from markupsafe import escape

from app.models.page import Page
from app.public import bp
from app.public.errors import not_found_response
from app.public.responses import content_security_policy, html_page
from app.services import contact_form, pages, preview, public_render
from app.services.errors import ServiceError
from app.services.permissions import Permission, has_permission
from app.services.render_context import RenderMode

PREVIEW_HEADERS = {
    "X-Frame-Options": "SAMEORIGIN",
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex",
}
ERROR_PAGE = (
    '<!doctype html><html lang="it"><head><meta charset="utf-8">'
    '<meta name="robots" content="noindex"><title>Anteprima non disponibile</title></head>'
    "<body><h1>Anteprima non disponibile</h1><p>{message}</p></body></html>"
)


CSRF_MESSAGE = "La sessione è cambiata: l'anteprima si aggiorna alla prossima modifica."
CSRF_STATUS = 403


def csrf_failed() -> Response:
    """Token CSRF scaduto: pagina d'errore che l'iframe del pannello può mostrare."""
    return _with_headers(html_page(ERROR_PAGE.format(message=escape(CSRF_MESSAGE)), CSRF_STATUS))


def _editable_page(page_id: int) -> Page | None:
    if not current_user.is_authenticated:
        return None
    if not has_permission(current_user._get_current_object(), Permission.CONTENT_EDIT):
        return None
    try:
        return pages.get_page(page_id)
    except ServiceError:
        return None


def _with_headers(response: Response) -> Response:
    for name, value in PREVIEW_HEADERS.items():
        response.headers[name] = value
    response.headers["Content-Security-Policy"] = content_security_policy("'self'")
    return response


def _render(page: Page, document: Mapping[str, Any]) -> Response:
    view = public_render.page_view(page, document)
    forms = contact_form.preview_forms(view)
    context = public_render.page_context(page, mode=RenderMode.PREVIEW, forms=forms, view=view)
    return _with_headers(html_page(public_render.renderer().render_page(context)))


@bp.route("/_preview/<int:page_id>", methods=["GET", "POST"])
def preview_page(page_id: int) -> Response:
    page = _editable_page(page_id)
    if page is None:
        return _with_headers(not_found_response())
    if request.method == "GET":
        return _render(page, preview.stored_document(page))
    try:
        document = preview.posted_document(request.form.get("document"))
    except ServiceError as exc:
        body = ERROR_PAGE.format(message=escape(exc.message))
        return _with_headers(html_page(body, exc.status))
    return _render(page, document)
