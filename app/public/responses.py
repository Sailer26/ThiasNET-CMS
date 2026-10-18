"""Header e risposte del sito pubblico (le API hanno i loro in app/api)."""

from __future__ import annotations

from urllib.parse import urlsplit

from flask import Flask, Request, Response, current_app, request
from werkzeug.wrappers import Response as BaseResponse

from app.api import API_PREFIX

PUBLIC_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",  # solo l'anteprima ammette SAMEORIGIN (D-55)
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
}
# Unici fornitori esterni ammessi negli iframe (D-60), gli stessi di consent.js.
EMBED_HOSTS = (
    "https://www.youtube-nocookie.com https://player.vimeo.com https://www.openstreetmap.org"
)
HTML = "text/html"


def _origin(url: str | None) -> str:
    parts = urlsplit(url or "")
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""


def content_security_policy(frame_ancestors: str = "'none'") -> str:
    """CSP del sito: niente script o stili inline (i temi non ne usano, D-59), statistiche
    solo dal server Matomo configurato (D-66), iframe solo verso i fornitori ammessi."""
    matomo = _origin(current_app.config.get("MATOMO_URL"))
    extra = f" {matomo}" if matomo else ""
    return "; ".join(
        [
            "default-src 'self'",
            f"script-src 'self'{extra}",
            f"connect-src 'self'{extra}",
            f"img-src 'self' data:{extra}",
            "style-src 'self'",
            f"frame-src {EMBED_HOSTS}",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            f"frame-ancestors {frame_ancestors}",
        ]
    )


def register(app: Flask) -> None:
    @app.after_request
    def _harden(response: Response) -> Response:
        if not request.path.startswith(API_PREFIX):
            for name, value in PUBLIC_SECURITY_HEADERS.items():
                response.headers.setdefault(name, value)
            response.headers.setdefault("Content-Security-Policy", content_security_policy())
        return response


def html_page(html: str, status: int = 200) -> Response:
    return Response(html, status=status, mimetype=HTML)


def conditional(response: Response, req: Request) -> BaseResponse:
    """ETag e 304: il browser ricontrolla sempre, ma riscarica solo se la pagina è cambiata."""
    response.headers["Cache-Control"] = "no-cache"
    response.add_etag()
    return response.make_conditional(req)
