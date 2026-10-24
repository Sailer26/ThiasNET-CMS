"""Notizie sul sito (Fase 7a, D-149): pagina elenco paginata, dettaglio, 301, sitemap."""

from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient

from tests.conftest import LoginAs
from tests.helpers import error_code
from tests.pages_helpers import PAGES, create_page, page_version, publish

NEWS = "/api/admin/collections/news/entries"
ENTRIES = "/api/admin/entries"


@pytest.fixture
def admin(login_as: LoginAs) -> FlaskClient:
    client, _ = login_as("admin")
    return client


@pytest.fixture
def visitor(app: Flask) -> FlaskClient:
    return app.test_client()


def listing(client: FlaskClient, title: str = "Notizie") -> dict[str, Any]:
    page = create_page(client, title, layout="news_list")
    assert publish(client, page["id"]).status_code == 200
    return page


def online_entry(
    client: FlaskClient, title: str, date: str = "2026-10-24", body: str = "<p>Ciao</p>"
) -> dict[str, Any]:
    created = client.post(NEWS, json={"title": title})
    assert created.status_code == 201, created.get_json()
    item: dict[str, Any] = created.get_json()["data"]
    version = client.get(f"{ENTRIES}/{item['id']}/draft").get_json()["data"]["version"]
    document = {"title": title, "fields": {"date": date, "body": body}, "seo": {}}
    saved = client.put(f"{ENTRIES}/{item['id']}/draft", json={"version": version, **document})
    assert saved.status_code == 200, saved.get_json()
    version = client.get(f"{ENTRIES}/{item['id']}/draft").get_json()["data"]["version"]
    published = client.post(f"{ENTRIES}/{item['id']}/publish", json={"draft_version": version})
    assert published.status_code == 200, published.get_json()
    return item


def test_listing_shows_online_entries_newest_first(
    admin: FlaskClient, visitor: FlaskClient
) -> None:
    page = listing(admin)
    online_entry(admin, "Vecchia", "2026-01-10")
    online_entry(admin, "Nuova", "2026-10-24")
    admin.post(NEWS, json={"title": "Ancora in bozza"})
    html = visitor.get(page["path"]).get_data(as_text=True)
    assert html.index("Nuova") < html.index("Vecchia")
    assert 'href="/notizie/nuova"' in html
    assert "Ancora in bozza" not in html
    assert "24 ottobre 2026" in html  # format_date in italiano


def test_collection_reports_its_listing_page(admin: FlaskClient) -> None:
    page = listing(admin)
    found = admin.get("/api/admin/collections").get_json()["data"][0]
    assert found["listing"] == {"page_id": page["id"], "path": "/notizie"}


def test_detail_page(admin: FlaskClient, visitor: FlaskClient) -> None:
    listing(admin)
    online_entry(admin, "Festa del paese", body="<p>Tutti <strong>in piazza</strong></p>")
    response = visitor.get("/notizie/festa-del-paese")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "<strong>in piazza</strong>" in html
    assert "<title>Festa del paese" in html
    assert 'href="/notizie"' in html  # briciole: torna all'elenco
    assert visitor.get("/notizie/non-esiste").status_code == 404


def test_drafts_and_trashed_entries_are_not_public(
    admin: FlaskClient, visitor: FlaskClient
) -> None:
    listing(admin)
    item = online_entry(admin, "Da togliere")
    current = admin.get(f"{ENTRIES}/{item['id']}").get_json()["data"]["version"]
    off = admin.post(f"{ENTRIES}/{item['id']}/unpublish", json={"version": current})
    assert off.status_code == 200
    assert visitor.get("/notizie/da-togliere").status_code == 404


def test_without_a_listing_page_entries_have_no_address(
    admin: FlaskClient, visitor: FlaskClient
) -> None:
    online_entry(admin, "Senza elenco")
    assert visitor.get("/senza-elenco").status_code == 404
    entry = admin.get(f"{NEWS}").get_json()["data"][0]
    assert entry["url"] is None


def test_pagination(admin: FlaskClient, visitor: FlaskClient) -> None:
    listing(admin)
    for n in range(11):  # per_page del tema: 10
        online_entry(admin, f"Notizia {n:02d}", f"2026-10-{n + 1:02d}")
    first = visitor.get("/notizie").get_data(as_text=True)
    assert "Notizia 10" in first and "Notizia 00" not in first
    assert 'href="/notizie?p=2"' in first
    second = visitor.get("/notizie?p=2")
    assert second.status_code == 200 and "Notizia 00" in second.get_data(as_text=True)
    assert 'href="/notizie"' in second.get_data(as_text=True)  # pagina precedente
    one = visitor.get("/notizie?p=1")
    assert one.status_code == 301 and one.headers["Location"].endswith("/notizie")
    padded = visitor.get("/notizie?p=02")
    assert padded.status_code == 301 and padded.headers["Location"].endswith("/notizie?p=2")
    for bad in ("3", "0", "abc", "{{7*7}}"):
        assert visitor.get(f"/notizie?p={bad}").status_code == 404, bad


def test_entries_follow_a_moved_listing_page(admin: FlaskClient, visitor: FlaskClient) -> None:
    page = listing(admin)
    online_entry(admin, "Festa")
    moved = admin.patch(
        f"{PAGES}/{page['id']}", json={"version": page_version(admin, page["id"]), "slug": "avvisi"}
    )
    assert moved.status_code == 200, moved.get_json()
    response = visitor.get("/notizie/festa")
    assert response.status_code == 301 and response.headers["Location"].endswith("/avvisi/festa")
    assert visitor.get("/avvisi/festa").status_code == 200


def test_one_listing_page_per_language(admin: FlaskClient) -> None:
    listing(admin)
    response = admin.post(PAGES, json={"title": "Altre notizie", "layout": "news_list"})
    assert (response.status_code, error_code(response)) == (409, "listing_exists")


def test_restoring_a_second_listing_page_is_refused(admin: FlaskClient) -> None:
    first = listing(admin)
    version = page_version(admin, first["id"])
    assert admin.delete(f"{PAGES}/{first['id']}", json={"version": version}).status_code == 200
    listing(admin, "Avvisi")
    trashed = admin.get(f"{PAGES}/trash").get_json()["data"]
    version = next(p["version"] for p in trashed if p["id"] == first["id"])
    back = admin.post(f"{PAGES}/{first['id']}/restore", json={"version": version})
    assert (back.status_code, error_code(back)) == (409, "listing_exists")


def test_homepage_cannot_be_the_listing(admin: FlaskClient) -> None:
    response = admin.post(PAGES, json={"title": "Home", "layout": "news_list", "slug": ""})
    assert (response.status_code, error_code(response)) == (422, "listing_not_home")


def test_listing_page_has_no_subpages(admin: FlaskClient) -> None:
    page = listing(admin)
    response = admin.post(PAGES, json={"title": "Sotto", "layout": "page", "parent_id": page["id"]})
    assert (response.status_code, error_code(response)) == (422, "listing_has_no_children")


def test_sitemap_lists_online_entries(admin: FlaskClient, visitor: FlaskClient) -> None:
    listing(admin)
    online_entry(admin, "Festa")
    body = visitor.get("/sitemap.xml").get_data(as_text=True)
    assert "/notizie/festa</loc>" in body


def test_new_entry_refreshes_the_cached_listing(admin: FlaskClient, visitor: FlaskClient) -> None:
    listing(admin)
    online_entry(admin, "Prima")
    assert "Prima" in visitor.get("/notizie").get_data(as_text=True)
    online_entry(admin, "Seconda")
    assert "Seconda" in visitor.get("/notizie").get_data(as_text=True)


def test_entry_text_is_data_not_template(admin: FlaskClient, visitor: FlaskClient) -> None:
    """Regola d'oro: i campi delle notizie non si eseguono mai come Jinja."""
    listing(admin)
    online_entry(admin, "Prova {{ 7*7 }}", body="<p>{% include 'x' %}</p>")
    html = visitor.get("/notizie/prova-7-7").get_data(as_text=True)
    assert '<h1 class="page-title">Prova {{ 7*7 }}</h1>' in html
    assert "<p>{% include 'x' %}</p>" in html  # testo, mai eseguito
