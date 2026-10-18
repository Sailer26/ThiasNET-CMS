"""Sito pubblico: indirizzi e lingue, redirect, 404, header, asset (D-50, D-51, D-62, D-65)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import update

from app.extensions import db
from app.models.page import Page
from tests.conftest import LoginAs
from tests.pages_helpers import (
    PAGES,
    create_page,
    doc,
    page_version,
    publish,
    put_draft,
    text_block,
)
from tests.render_fixtures import inspect


@pytest.fixture
def admin(login_as: LoginAs) -> FlaskClient:
    client, _ = login_as("admin")
    return client


@pytest.fixture
def visitor(app: Flask) -> FlaskClient:
    return app.test_client()


def _online(
    client: FlaskClient, title: str, body: str = "<p>Testo</p>", **extra: Any
) -> dict[str, Any]:
    page = create_page(client, title, **extra)
    layout = "home" if extra.get("slug") == "" else "page"
    zones = (
        {"hero": [], "main": [text_block(1, body)]}
        if layout == "home"
        else {
            "main": [text_block(1, body)],
            "sidebar": [],
        }
    )
    assert (
        put_draft(client, page["id"], doc(title=title, layout=layout, zones=zones)).status_code
        == 200
    )
    assert publish(client, page["id"]).status_code == 200
    return page


def _patch(client: FlaskClient, page_id: int, **changes: Any) -> Any:
    body = {"version": page_version(client, page_id), **changes}
    return client.patch(f"{PAGES}/{page_id}", json=body)


# --- Pagine e lingue ------------------------------------------------------------------


def test_published_pages_are_served(admin: FlaskClient, visitor: FlaskClient) -> None:
    _online(admin, "Home", layout="home", slug="")
    _online(admin, "Chi siamo", "<p>Siamo un comune</p>")
    home = visitor.get("/")
    assert home.status_code == 200
    assert home.mimetype == "text/html"
    page = visitor.get("/chi-siamo")
    assert page.status_code == 200
    assert "Siamo un comune" in page.get_data(as_text=True)


def test_other_languages_have_a_prefix(admin: FlaskClient, visitor: FlaskClient) -> None:
    _online(admin, "Über uns", locale="de")
    _online(admin, "Start", layout="home", slug="", locale="de")
    assert visitor.get("/de/ueber-uns").status_code == 200
    html = visitor.get("/de/").get_data(as_text=True)
    assert '<html lang="de">' in html
    assert visitor.get("/ueber-uns").status_code == 404


@pytest.mark.parametrize(
    ("path", "location"),
    [("/de", "/de/"), ("/it/chi-siamo", "/chi-siamo"), ("/it", "/"), ("/chi-siamo/", "/chi-siamo")],
)
def test_canonical_redirects(visitor: FlaskClient, path: str, location: str) -> None:
    response = visitor.get(path)
    assert response.status_code == 301
    assert response.headers["Location"] == location


def test_drafts_and_trash_are_never_shown(admin: FlaskClient, visitor: FlaskClient) -> None:
    create_page(admin, "Bozza")
    online = _online(admin, "Cestinata")
    admin.delete(f"{PAGES}/{online['id']}", json={"version": page_version(admin, online["id"])})
    assert visitor.get("/bozza").status_code == 404
    assert visitor.get("/cestinata").status_code == 404


@pytest.mark.parametrize("path", ["/Chi-Siamo", "/chi%20siamo", "/a" * 200, "/x.php"])
def test_invalid_paths_are_404(visitor: FlaskClient, path: str) -> None:
    assert visitor.get(path).status_code == 404


def test_not_found_uses_the_theme(visitor: FlaskClient) -> None:
    response = visitor.get("/non-esiste")
    assert response.status_code == 404
    html = response.get_data(as_text=True)
    assert "Pagina non trovata" in html
    assert {"name": "robots", "content": "noindex"} in inspect(html).find("meta")


def test_api_paths_keep_json_errors(visitor: FlaskClient) -> None:
    response = visitor.get("/api/non-esiste")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_head_requests_work(admin: FlaskClient, visitor: FlaskClient) -> None:
    _online(admin, "Chi siamo")
    response = visitor.head("/chi-siamo")
    assert response.status_code == 200
    assert response.get_data() == b""


# --- Redirect e programmazione (D-51) --------------------------------------------------


def test_old_addresses_redirect_only_to_online_pages(
    admin: FlaskClient, visitor: FlaskClient
) -> None:
    page = _online(admin, "Orari")
    _patch(admin, page["id"], slug="orari-apertura")
    moved = visitor.get("/orari")
    assert (moved.status_code, moved.headers["Location"]) == (301, "/orari-apertura")
    admin.post(f"{PAGES}/{page['id']}/unpublish", json={"version": page_version(admin, page["id"])})
    assert visitor.get("/orari").status_code == 404


def test_redirect_drops_the_query_string(admin: FlaskClient, visitor: FlaskClient) -> None:
    page = _online(admin, "Orari")
    _patch(admin, page["id"], slug="aperture")
    assert visitor.get("/orari?x=1").headers["Location"] == "/aperture"


def test_due_schedule_is_published_on_request(
    app: Flask, admin: FlaskClient, visitor: FlaskClient
) -> None:
    page = create_page(admin, "Evento")
    when = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    admin.post(f"{PAGES}/{page['id']}/schedule", json={"draft_version": 1, "publish_at": when})
    assert visitor.get("/evento").status_code == 404
    with app.app_context():
        past = datetime.now(UTC) - timedelta(minutes=1)
        db.session.execute(update(Page).where(Page.id == page["id"]).values(publish_at=past))
        db.session.commit()
    assert visitor.get("/evento").status_code == 200


# --- Contenuto, SEO di base e menu ----------------------------------------------------------


def test_canonical_never_trusts_the_host_header(admin: FlaskClient, visitor: FlaskClient) -> None:
    _online(admin, "Chi siamo")
    html = visitor.get("/chi-siamo", headers={"Host": "evil.example"}).get_data(as_text=True)
    assert {"rel": "canonical", "href": "https://www.example.ch/chi-siamo"} in inspect(html).find(
        "link"
    )
    assert "evil.example" not in html


def test_menu_and_breadcrumbs(admin: FlaskClient, visitor: FlaskClient) -> None:
    _online(admin, "Home", layout="home", slug="")
    parent = _online(admin, "Servizi")
    _online(admin, "Scuola", parent_id=parent["id"])
    create_page(admin, "Bozza nel menu")
    page = inspect(visitor.get("/servizi/scuola").get_data(as_text=True))
    links = {a.get("href") for a in page.find("a")}
    assert {"/", "/servizi"} <= links
    assert "/bozza-nel-menu" not in links
    current = [a for _, a in page.tags if a.get("aria-current") == "page"]
    assert current  # la voce di menu della sezione e la briciola della pagina


def test_security_headers_on_public_pages(admin: FlaskClient, visitor: FlaskClient) -> None:
    _online(admin, "Chi siamo")
    headers = visitor.get("/chi-siamo").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in headers["Permissions-Policy"]


def test_server_error_page_is_static(
    app: Flask, visitor: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("errore simulato")

    monkeypatch.setattr("app.services.public_pages.resolve", boom)
    app.config["PROPAGATE_EXCEPTIONS"] = False
    response = visitor.get("/qualsiasi")
    assert response.status_code == 500
    assert "errore simulato" not in response.get_data(as_text=True)
    assert response.mimetype == "text/html"


# --- Asset del tema e colori ---------------------------------------------------------------


def test_theme_assets_are_served_with_long_cache(visitor: FlaskClient) -> None:
    response = visitor.get("/assets/css/site.css?v=123")
    assert response.status_code == 200
    assert response.mimetype == "text/css"
    assert "max-age=31536000" in response.headers["Cache-Control"]


@pytest.mark.parametrize(
    "path",
    ["/assets/../theme.json", "/assets/theme.json", "/assets/css/.hidden.css", "/assets/x.html"],
)
def test_only_theme_assets_can_be_downloaded(visitor: FlaskClient, path: str) -> None:
    assert visitor.get(path).status_code == 404


def test_css_variables_from_theme_settings(visitor: FlaskClient) -> None:
    response = visitor.get("/_vars.css")
    assert response.status_code == 200
    assert response.mimetype == "text/css"
    assert "--accent-color: #0B5FFF;" in response.get_data(as_text=True)


# --- Sitemap e robots (D-62) -------------------------------------------------------------

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def test_sitemap_lists_only_indexable_online_pages(
    admin: FlaskClient, visitor: FlaskClient
) -> None:
    import xml.etree.ElementTree as ET

    _online(admin, "Home", layout="home", slug="")
    _online(admin, "Über uns", locale="de")
    hidden = _online(admin, "Nascosta")
    zones = {"main": [text_block(1)], "sidebar": []}
    put_draft(
        admin, hidden["id"], doc(title="Nascosta", zones=zones, seo={"noindex": True}), version=0
    )
    publish(admin, hidden["id"])
    create_page(admin, "Bozza")

    response = visitor.get("/sitemap.xml")
    assert response.status_code == 200
    assert response.mimetype == "application/xml"
    root = ET.fromstring(response.get_data())  # noqa: S314
    locations = {loc.text for loc in root.iter(f"{SITEMAP_NS}loc")}
    assert locations == {"https://www.example.ch/", "https://www.example.ch/de/ueber-uns"}
    assert all(lastmod.text for lastmod in root.iter(f"{SITEMAP_NS}lastmod"))


def test_robots_blocks_everything_outside_production(visitor: FlaskClient) -> None:
    response = visitor.get("/robots.txt")
    assert response.mimetype == "text/plain"
    assert response.get_data(as_text=True) == "User-agent: *\nDisallow: /\n"


def test_robots_in_production_points_to_the_sitemap(app: Flask, visitor: FlaskClient) -> None:
    app.config["ROBOTS_ALLOW_INDEXING"] = True
    body = visitor.get("/robots.txt").get_data(as_text=True)
    assert "Disallow: /_preview/" in body and "Disallow: /api/" in body
    assert "Sitemap: https://www.example.ch/sitemap.xml" in body
    assert "Disallow: /\n" not in body


# --- Consenso e statistiche (D-60, D-66) -----------------------------------------------------


def test_stats_choice_appears_only_with_matomo(
    app: Flask, admin: FlaskClient, visitor: FlaskClient
) -> None:
    _online(admin, "Chi siamo")
    without = inspect(visitor.get("/chi-siamo").get_data(as_text=True))
    assert not [a for a in without.find("input") if a.get("name") == "stats"]
    app.config.update(MATOMO_URL="https://stat.thiasnet.ch", MATOMO_SITE_ID="7")
    with app.app_context():
        from app.services import page_cache

        page_cache.mark_changed()
        db.session.commit()
    page = inspect(visitor.get("/chi-siamo").get_data(as_text=True))
    assert [a for a in page.find("input") if a.get("name") == "stats"]
    consent = [
        s for s in page.find("script") if (s.get("src") or "").startswith("/static/cms/consent.js")
    ]
    assert consent[0]["data-matomo-url"] == "https://stat.thiasnet.ch"
    assert consent[0]["data-matomo-site"] == "7"


# --- Accessibilità di base (WCAG 2.1 AA sul tema default) -----------------------------------


def test_accessibility_smoke(admin: FlaskClient, visitor: FlaskClient) -> None:
    from tests.unit.test_blocks_registry import VALID

    page = create_page(admin, "Tutto")
    blocks = [
        {"uid": f"{n:032x}", "type": block_type, "data": data}
        for n, (block_type, data) in enumerate(sorted(VALID.items()), start=1)
        if block_type != "hero"
    ]
    put_draft(admin, page["id"], doc(title="Tutto", zones={"main": blocks, "sidebar": []}))
    assert publish(admin, page["id"]).status_code == 200
    html = visitor.get("/tutto").get_data(as_text=True)
    found = inspect(html)

    assert found.find("html")[0]["lang"] == "it"
    assert len(found.find("h1")) == 1
    skip = found.find("a")[0]
    assert skip["href"] == "#main" and {"id": "main", "tabindex": "-1"} in found.find("main")
    labels = {a.get("for") for a in found.find("label")}
    for field in found.find("input") + found.find("textarea"):
        if field.get("type") in {"hidden", "checkbox"}:
            continue
        assert field.get("id") in labels, field
    dialog = next(a for _, a in found.tags if a.get("role") == "dialog")
    assert dialog["aria-labelledby"] == "cms-consent-title"
    choices = {a.get("data-cms-consent") for a in found.find("button")}
    assert {"all", "necessary", "choose"} <= choices
