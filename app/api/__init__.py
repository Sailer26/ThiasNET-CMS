"""Risposte JSON standard per le API: {success, data, error, meta?}."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import Flask, Response, jsonify, request
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException

from app.services.errors import ServiceError

API_PREFIX = "/api/"
HTTP_MESSAGES = {
    400: ("bad_request", "Richiesta non valida"),
    401: ("unauthorized", "Accesso richiesto"),
    403: ("forbidden", "Non hai i permessi per questa operazione"),
    404: ("not_found", "Risorsa non trovata"),
    405: ("method_not_allowed", "Operazione non consentita"),
    413: ("too_large", "Il file o la richiesta sono troppo grandi"),
    429: ("rate_limited", "Troppe richieste: riprova tra qualche minuto"),
    500: ("server_error", "Si è verificato un errore: riprova più tardi"),
}


def ok(data: Any = None, *, status: int = 200, meta: Mapping[str, Any] | None = None) -> Response:
    body: dict[str, Any] = {"success": True, "data": data, "error": None}
    if meta is not None:
        body["meta"] = dict(meta)
    response = jsonify(body)
    response.status_code = status
    return response


def fail(
    code: str,
    message: str,
    status: int,
    *,
    retry_after: int | None = None,
    details: Any = None,
) -> Response:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    response = jsonify({"success": False, "data": None, "error": error})
    response.status_code = status
    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
    return response


def unauthorized() -> Response:
    code, message = HTTP_MESSAGES[401]
    return fail(code, message, 401)


API_SECURITY_HEADERS = {
    "Cache-Control": "no-store",  # dati del pannello mai in cache (browser o proxy)
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


def register_response_headers(app: Flask) -> None:
    """Header di sicurezza sulle API. CSP e HSTS del sito arrivano in Fase 8 (Caddy)."""

    @app.after_request
    def _harden(response: Response) -> Response:
        if request.path.startswith(API_PREFIX):
            for name, value in API_SECURITY_HEADERS.items():
                response.headers.setdefault(name, value)
        return response


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ServiceError)
    def _service_error(exc: ServiceError) -> Response:
        return fail(
            exc.code, exc.message, exc.status, retry_after=exc.retry_after, details=exc.details
        )

    @app.errorhandler(CSRFError)
    def _csrf_error(_exc: CSRFError) -> Response:
        # 403 (non 400): un test che accetta 400 non passa "per sbaglio" a causa del CSRF.
        return fail("csrf", "Sessione scaduta o richiesta non valida: ricarica la pagina", 403)

    @app.errorhandler(HTTPException)
    def _http_error(exc: HTTPException) -> Response:
        if not request.path.startswith(API_PREFIX):
            from app.public.errors import html_error  # il sito ha le sue pagine d'errore

            return html_error(exc)
        status = exc.code or 500
        code, message = HTTP_MESSAGES.get(status, ("error", "Richiesta non valida"))
        return fail(code, message, status)
