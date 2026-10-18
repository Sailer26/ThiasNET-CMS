"""Invio del modulo contatti (D-61).

Le pagine del sito sono anonime e senza sessione, quindi qui non c'è il token CSRF della
sessione: al suo posto controllo dell'origine (`Origin`/`Referer` contro SITE_URL) e token
firmato del modulo, valido per una sola pagina e un solo blocco.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from flask import Response, redirect, request
from markupsafe import escape
from werkzeug.wrappers import Response as BaseResponse

from app.extensions import csrf
from app.models.page import Page
from app.public import bp
from app.public.responses import html_page
from app.services import contact_form, public_pages, public_render, site_settings
from app.services.contact_form import Outcome, Submission
from app.services.public_texts import text
from app.services.theme import active_theme

MESSAGE_PAGE = (
    '<!doctype html><html lang="{locale}"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">'
    '<meta name="robots" content="noindex"><title>{message}</title></head>'
    '<body><p>{message}</p><p><a href="{back}">&larr;</a></p></body></html>'
)


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""


def _same_origin() -> bool:
    expected = _origin(site_settings.current().base_url)
    sent = request.headers.get("Origin") or _origin(request.headers.get("Referer", ""))
    return bool(expected) and sent == expected


def _message_page(key: str, status: int, locale: str, back: str = "/") -> Response:
    body = MESSAGE_PAGE.format(
        locale=escape(locale), message=escape(text(key, locale)), back=escape(back)
    )
    response = html_page(body, status)
    response.headers["Cache-Control"] = "no-store"
    return response


def _rerender(page: Page, result: Submission) -> Response:
    view = public_render.page_view(page)
    forms = contact_form.public_forms(view, failed=result)
    context = public_render.page_context(page, forms=forms, view=view)
    response = html_page(public_render.renderer().render_page(context), 422)
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/_contact")
def contact() -> BaseResponse:
    default = active_theme().locales[0]
    request.max_content_length = contact_form.MAX_BODY_BYTES  # vale anche senza Content-Length
    if (request.content_length or 0) > contact_form.MAX_BODY_BYTES:
        return _message_page("contact_errors", 413, default)
    if not _same_origin():
        return _message_page("contact_expired", 403, default)
    result = contact_form.submit(request.form.to_dict(), request.remote_addr)
    if result.page is None:
        return _message_page("contact_expired", 422, default)
    back = public_pages.public_url(result.page, active_theme())
    if result.outcome in {Outcome.SENT, Outcome.IGNORED}:
        return redirect(f"{back}?contatto=inviato#contatti-{result.uid}", code=303)
    if result.outcome is Outcome.INVALID_FIELDS:
        return _rerender(result.page, result)
    response = _message_page("contact_too_many", 429, result.page.locale, back)
    response.headers["Retry-After"] = str(result.retry_after or 600)
    return response


csrf.exempt(contact)  # pagine anonime: al posto del CSRF di sessione, origine + token del modulo
