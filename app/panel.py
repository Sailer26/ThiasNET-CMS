"""Pannello admin: Flask serve la SPA compilata su /admin/ (D-87). Solo GET, nessun Jinja."""

from __future__ import annotations

from flask import Blueprint, Response, send_file
from werkzeug.wrappers import Response as BaseResponse

from app.services import panel_assets

bp = Blueprint("panel", __name__, url_prefix="/admin")
ONE_YEAR = 365 * 24 * 3600
ASSETS = "assets/"


def _not_found() -> BaseResponse:
    """404 semplice: un file mancante del pannello non è una pagina del sito."""
    return Response("Non trovato", 404, mimetype="text/plain")


def _harden(response: BaseResponse) -> BaseResponse:
    response.headers.update(panel_assets.PANEL_HEADERS)
    return response


@bp.get("/", defaults={"subpath": ""})
@bp.get("/<path:subpath>")
def spa(subpath: str) -> BaseResponse:
    """Ogni indirizzo del pannello riceve lo stesso index.html: le schermate sono della SPA."""
    if subpath == ASSETS.rstrip("/") or subpath.startswith(ASSETS):
        return _not_found()  # i file della build non ricadono mai su index.html
    index = panel_assets.index_file()
    if index is None:
        return _harden(Response(panel_assets.MISSING_BUILD, 503, mimetype="text/plain"))
    response = send_file(index, mimetype="text/html", max_age=0)
    response.headers["Cache-Control"] = "no-cache"  # dopo un deploy il browser ricontrolla
    return _harden(response)


@bp.get("/assets/<path:filename>")
def asset(filename: str) -> BaseResponse:
    path = panel_assets.asset_path(filename)
    if path is None:
        return _not_found()
    response = send_file(path, max_age=ONE_YEAR)
    response.headers["Cache-Control"] = f"public, max-age={ONE_YEAR}, immutable"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
