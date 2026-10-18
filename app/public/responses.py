"""Header e risposte del sito pubblico (le API hanno i loro in app/api)."""

from __future__ import annotations

from flask import Flask, Request, Response, request
from werkzeug.wrappers import Response as BaseResponse

from app.api import API_PREFIX

PUBLIC_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",  # solo l'anteprima ammette SAMEORIGIN (D-55)
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
}
HTML = "text/html"


def register(app: Flask) -> None:
    @app.after_request
    def _harden(response: Response) -> Response:
        if not request.path.startswith(API_PREFIX):
            for name, value in PUBLIC_SECURITY_HEADERS.items():
                response.headers.setdefault(name, value)
        return response


def html_page(html: str, status: int = 200) -> Response:
    return Response(html, status=status, mimetype=HTML)


def conditional(response: Response, req: Request) -> BaseResponse:
    """ETag e 304: il browser ricontrolla sempre, ma riscarica solo se la pagina è cambiata."""
    response.headers["Cache-Control"] = "no-cache"
    response.add_etag()
    return response.make_conditional(req)
