"""Route del sito: pagine, asset del tema e variabili CSS (D-50, D-51, D-59)."""

from __future__ import annotations

from datetime import UTC, datetime

from flask import Response, abort, redirect, request, send_from_directory
from werkzeug.wrappers import Response as BaseResponse

from app.public import bp
from app.public.errors import not_found_response
from app.public.responses import conditional, html_page
from app.services import public_pages, public_render, site_settings
from app.services.public_pages import Outcome
from app.services.render import asset_path_is_valid
from app.services.theme import active_theme

# Primi segmenti che non sono mai pagine: errore 404 (JSON sotto /api, gestito altrove).
RESERVED_SEGMENTS = frozenset({"api", "admin", "static", "media", "assets"})
LONG_CACHE = 365 * 24 * 3600
SHORT_CACHE = 3600


@bp.get("/", defaults={"path": ""})
@bp.get("/<path:path>")
def page(path: str) -> BaseResponse:
    if path.split("/", 1)[0] in RESERVED_SEGMENTS:
        abort(404)
    theme = active_theme()
    resolution = public_pages.resolve(request.path, theme, datetime.now(UTC))
    if resolution.outcome is Outcome.REDIRECT and resolution.location:
        return redirect(resolution.location, code=301)
    if resolution.outcome is Outcome.NOT_FOUND or resolution.page is None:
        return not_found_response(resolution.locale)
    context = public_render.page_context(resolution.page)
    html = public_render.renderer().render_page(context)
    return conditional(html_page(html), request)


@bp.get("/assets/<path:filename>")
def theme_asset(filename: str) -> Response:
    """Solo file statici del tema con estensioni ammesse; mai template o theme.json."""
    if not asset_path_is_valid(filename):
        abort(404)
    max_age = LONG_CACHE if request.args.get("v") else SHORT_CACHE
    return send_from_directory(active_theme().directory / "assets", filename, max_age=max_age)


@bp.get("/_vars.css")
def css_variables() -> Response:
    theme = active_theme()
    css = site_settings.css_variables(theme, site_settings.theme_settings(theme))
    response = Response(css, mimetype="text/css")
    response.headers["Cache-Control"] = (
        f"public, max-age={LONG_CACHE}, immutable" if request.args.get("v") else "no-cache"
    )
    return response
