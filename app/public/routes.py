"""Route del sito: pagine, asset del tema e variabili CSS (D-50, D-51, D-59)."""

from __future__ import annotations

from datetime import UTC, datetime

from flask import Response, abort, current_app, redirect, request, send_from_directory
from werkzeug.wrappers import Response as BaseResponse

from app.public import bp
from app.public.errors import not_found_response
from app.public.responses import conditional, html_page
from app.services import (
    contact_form,
    page_cache,
    public_pages,
    public_render,
    seo,
    site_settings,
    widgets,
)
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
    widgets.expire_due()  # banner scaduto: la cache si rinnova prima di leggerla (D-146)
    # Prima la generazione, poi la pagina: il contenuto letto dopo è almeno altrettanto nuovo,
    # quindi in cache non finisce mai una pagina vecchia con un numero nuovo (D-54).
    generation = page_cache.current_generation()
    resolution = public_pages.resolve(request.path, theme, datetime.now(UTC))
    if resolution.outcome is Outcome.REDIRECT and resolution.location:
        return redirect(resolution.location, code=301)
    if resolution.outcome is Outcome.NOT_FOUND or resolution.page is None:
        return not_found_response(resolution.locale)
    page = resolution.page
    key = (theme.name, theme.version, page.locale, page.path)
    cache = page_cache.page_cache()
    html = cache.get(key, generation)
    if html is not None:
        return conditional(html_page(html), request)
    view = public_render.page_view(page)
    forms = contact_form.public_forms(view, sent=request.args.get("contatto") == "inviato")
    context = public_render.page_context(page, forms=forms, view=view)
    html = public_render.renderer().render_page(context)
    if not public_render.cacheable(context):  # modulo contatti: token nuovo a ogni visita
        response = html_page(html)
        response.headers["Cache-Control"] = "no-store"
        return response
    cache.put(key, html, generation)
    return conditional(html_page(html), request)


@bp.get("/assets/<path:filename>")
def theme_asset(filename: str) -> Response:
    """Solo file statici del tema con estensioni ammesse; mai template o theme.json."""
    assets = (active_theme().directory / "assets").resolve()
    if not asset_path_is_valid(filename) or not (assets / filename).resolve().is_relative_to(
        assets
    ):
        abort(404)  # anche i collegamenti simbolici che escono da assets/
    version = public_render.renderer().asset_version(filename)
    fresh = version is not None and request.args.get("v") == version
    return send_from_directory(assets, filename, max_age=LONG_CACHE if fresh else SHORT_CACHE)


@bp.get("/_vars.css")
def css_variables() -> Response:
    theme = active_theme()
    css = site_settings.css_variables(theme, site_settings.theme_settings(theme))
    response = Response(css, mimetype="text/css")
    fresh = request.args.get("v") == site_settings.css_version(css)  # mai "per sempre" a caso
    response.headers["Cache-Control"] = (
        f"public, max-age={LONG_CACHE}, immutable" if fresh else "no-cache"
    )
    return response


@bp.get("/sitemap.xml")
def sitemap() -> Response:
    settings = site_settings.current()
    body = seo.sitemap_xml(active_theme(), settings.base_url)
    response = Response(body, mimetype="application/xml")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@bp.get("/robots.txt")
def robots() -> Response:
    settings = site_settings.current()
    allow = bool(current_app.config["ROBOTS_ALLOW_INDEXING"])
    return Response(seo.robots_txt(settings.base_url, allow_indexing=allow), mimetype="text/plain")
