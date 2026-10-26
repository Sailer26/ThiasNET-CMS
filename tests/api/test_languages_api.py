"""Lingue (Fase 7c, D-151, D-158 … D-161): traduzioni collegate, lingua del pannello, selettore,
hreflang e sitemap."""

from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient

from tests.conftest import LoginAs
from tests.helpers import API, error_code
from tests.pages_helpers import (
    PAGES,
    create_page,
    doc,
    get_draft,
    page_version,
    publish,
    put_draft,
    text_block,
)

ENTRIES = f"{API}/entries"


@pytest.fixture
def admin(login_as: LoginAs) -> FlaskClient:
    client, _ = login_as("admin")
    return client


@pytest.fixture
def visitor(app: Flask) -> FlaskClient:
    return app.test_client()


def translate(client: FlaskClient, page_id: int, locale: str = "de") -> Any:
    return client.post(f"{PAGES}/{page_id}/translations", json={"locale": locale})


def online_page(client: FlaskClient, title: str, **extra: Any) -> dict[str, Any]:
    page = create_page(client, title, **extra)
    assert publish(client, page["id"]).status_code == 200
    return page


def home(client: FlaskClient) -> dict[str, Any]:
    return online_page(client, "Home", slug="")


def publish_translation(
    client: FlaskClient, page_id: int, title: str, locale: str = "de"
) -> dict[str, Any]:
    response = translate(client, page_id, locale)
    assert response.status_code == 201, response.get_json()
    created: dict[str, Any] = response.get_json()["data"]
    layout = get_draft(client, created["id"])["data"]["layout"]
    zones: dict[str, list[Any]] = (
        {"main": [], "sidebar": []} if layout == "page" else {"hero": [], "main": []}
    )
    assert (
        put_draft(client, created["id"], doc(title=title, layout=layout, zones=zones)).status_code
        == 200
    )
    assert publish(client, created["id"]).status_code == 200
    return created


# --- traduzioni ---------------------------------------------------------------------------------


def test_translation_copies_the_draft_into_the_other_language(admin: FlaskClient) -> None:
    page = create_page(admin, "Chi siamo")
    zones = {"main": [text_block(1, "<p>Ciao</p>")], "sidebar": []}
    assert put_draft(admin, page["id"], doc(title="Chi siamo", zones=zones)).status_code == 200
    response = translate(admin, page["id"])
    assert response.status_code == 201, response.get_json()
    created = response.get_json()["data"]
    assert created["locale"] == "de" and created["status"] == "draft"
    assert created["path"] == "/chi-siamo"
    copied = get_draft(admin, created["id"])["data"]
    assert copied["zones"]["main"][0]["data"]["body"] == "<p>Ciao</p>"
    again = translate(admin, page["id"])
    assert (again.status_code, error_code(again)) == (409, "translation_exists")
    listed = admin.get(f"{PAGES}/{page['id']}/translations").get_json()["data"]
    by_locale = {row["locale"]: row for row in listed}
    assert by_locale["it"]["id"] == page["id"] and by_locale["de"]["id"] == created["id"]
    assert by_locale["en"]["id"] is None and by_locale["de"]["label"] == "Deutsch"


@pytest.mark.parametrize(("locale", "code"), [("it", "same_locale"), ("fr", "unknown_locale")])
def test_translation_needs_another_active_language(
    admin: FlaskClient, locale: str, code: str
) -> None:
    page = create_page(admin, "Chi siamo")
    response = translate(admin, page["id"], locale)
    assert (response.status_code, error_code(response)) == (422, code)


def test_subpage_goes_under_the_translated_parent(admin: FlaskClient) -> None:
    parent = create_page(admin, "Servizi")
    child = create_page(admin, "Acqua", parent_id=parent["id"])
    orphan = translate(admin, child["id"]).get_json()["data"]
    assert orphan["parent_id"] is None  # la pagina superiore non è ancora tradotta: primo livello
    parent_de = translate(admin, parent["id"]).get_json()["data"]
    other = create_page(admin, "Gas", parent_id=parent["id"])
    child_de = translate(admin, other["id"]).get_json()["data"]
    assert child_de["parent_id"] == parent_de["id"] and child_de["path"] == "/servizi/gas"


def test_home_translation_is_the_home_of_that_language(
    admin: FlaskClient, visitor: FlaskClient
) -> None:
    it_home = home(admin)
    publish_translation(admin, it_home["id"], "Startseite")
    response = visitor.get("/de/")
    assert response.status_code == 200 and "Startseite" in response.get_data(as_text=True)


def test_entry_translation(admin: FlaskClient) -> None:
    news = f"{API}/collections/news/entries"
    created = admin.post(news, json={"title": "Festa"}).get_json()["data"]
    response = admin.post(f"{ENTRIES}/{created['id']}/translations", json={"locale": "de"})
    assert response.status_code == 201, response.get_json()
    entry_de = response.get_json()["data"]
    assert (entry_de["locale"], entry_de["slug"], entry_de["collection"]) == ("de", "festa", "news")
    listed = admin.get(f"{ENTRIES}/{created['id']}/translations").get_json()["data"]
    assert {row["locale"]: row["id"] for row in listed}["de"] == entry_de["id"]


def test_restoring_a_duplicate_translation_is_refused(admin: FlaskClient) -> None:
    page = create_page(admin, "Chi siamo")
    first = translate(admin, page["id"]).get_json()["data"]
    trashed = admin.delete(
        f"{PAGES}/{first['id']}", json={"version": page_version(admin, first["id"])}
    )
    assert trashed.status_code == 200
    assert translate(admin, page["id"]).status_code == 201  # la prima è nel cestino
    found = admin.get(f"{PAGES}/trash").get_json()["data"]
    version = next(p["version"] for p in found if p["id"] == first["id"])
    back = admin.post(f"{PAGES}/{first['id']}/restore", json={"version": version})
    assert (back.status_code, error_code(back)) == (409, "translation_exists")


def test_trashing_the_original_keeps_the_translation(
    admin: FlaskClient, visitor: FlaskClient
) -> None:
    """D-161: ogni lingua è una pagina a sé."""
    it_home = home(admin)
    publish_translation(admin, it_home["id"], "Startseite")
    page = online_page(admin, "Chi siamo")
    publish_translation(admin, page["id"], "Über uns")
    version = page_version(admin, page["id"])
    assert admin.delete(f"{PAGES}/{page['id']}", json={"version": version}).status_code == 200
    assert visitor.get("/de/chi-siamo").status_code == 200


# --- lingua del pannello -------------------------------------------------------------------------


def test_panel_screens_follow_the_chosen_language(admin: FlaskClient) -> None:
    create_page(admin, "Chi siamo")
    assert admin.get(f"{PAGES}/tree?locale=de").get_json()["data"] == []
    tree_it = admin.get(f"{PAGES}/tree?locale=it").get_json()["data"]
    assert [n["title"] for n in tree_it] == ["Chi siamo"]
    assert admin.get(f"{PAGES}/tree?locale=fr").status_code == 422
    footer_de = {"uid": "a" * 32, "type": "text", "data": {"body": "<p>Hallo</p>"}}
    stored = admin.put(f"{API}/widgets/footer?locale=de", json={"version": 0, "items": [footer_de]})
    assert stored.status_code == 200, stored.get_json()
    widgets_it = {a["area"]: a for a in admin.get(f"{API}/widgets?locale=it").get_json()["data"]}
    widgets_de = {a["area"]: a for a in admin.get(f"{API}/widgets?locale=de").get_json()["data"]}
    assert widgets_it["footer"]["items"] == [] and len(widgets_de["footer"]["items"]) == 1
    assert widgets_de["footer"]["locale"] == "de"
    menus_de = {m["location"]: m for m in admin.get(f"{API}/menus?locale=de").get_json()["data"]}
    assert menus_de["main"]["items"] == []
    news = f"{API}/collections/news/entries"
    admin.post(news, json={"title": "Neu", "locale": "de"})
    news_de = admin.get(f"{news}?locale=de").get_json()["data"]
    news_it = admin.get(f"{news}?locale=it").get_json()["data"]
    assert [e["title"] for e in news_de] == ["Neu"] and news_it == []


# --- sito: selettore, hreflang, sitemap --------------------------------------------------------------


def test_switcher_and_hreflang_point_to_the_translation(
    admin: FlaskClient, visitor: FlaskClient
) -> None:
    it_home = home(admin)
    publish_translation(admin, it_home["id"], "Startseite")
    page = online_page(admin, "Chi siamo")
    publish_translation(admin, page["id"], "Über uns")
    html = visitor.get("/chi-siamo").get_data(as_text=True)
    assert 'hreflang="de" href="/de/chi-siamo"' in html  # selettore della lingua
    assert '<link rel="alternate" hreflang="it" href="http' in html
    assert '<link rel="alternate" hreflang="de" href="http' in html and "/de/chi-siamo" in html
    assert 'hreflang="x-default"' in html


def test_without_a_translation_the_switcher_goes_home(
    admin: FlaskClient, visitor: FlaskClient
) -> None:
    """D-151: senza traduzione, la homepage di quella lingua; nessun hreflang verso di lei."""
    it_home = home(admin)
    publish_translation(admin, it_home["id"], "Startseite")
    online_page(admin, "Solo italiano")
    html = visitor.get("/solo-italiano").get_data(as_text=True)
    assert 'hreflang="de" href="/de/"' in html
    assert '<link rel="alternate" hreflang="de"' not in html


def test_a_language_without_its_home_stays_hidden(admin: FlaskClient, visitor: FlaskClient) -> None:
    """D-158: una lingua compare solo con la sua homepage online; con una sola lingua, niente."""
    home(admin)
    page = online_page(admin, "Chi siamo")
    created = translate(admin, page["id"]).get_json()["data"]
    assert publish(admin, created["id"]).status_code == 200
    html = visitor.get("/chi-siamo").get_data(as_text=True)
    assert 'hreflang="de"' not in html
    assert "language-switcher" not in html


def test_sitemap_lists_the_alternates(admin: FlaskClient, visitor: FlaskClient) -> None:
    it_home = home(admin)
    publish_translation(admin, it_home["id"], "Startseite")
    body = visitor.get("/sitemap.xml").get_data(as_text=True)
    assert 'xmlns:xhtml="http://www.w3.org/1999/xhtml"' in body
    assert '<xhtml:link rel="alternate" hreflang="de"' in body


def test_latest_entries_follow_the_page_language(admin: FlaskClient, visitor: FlaskClient) -> None:
    it_home = home(admin)
    publish_translation(admin, it_home["id"], "Startseite")
    news = f"{API}/collections/news/entries"
    for locale, title in (("it", "Notizia italiana"), ("de", "Deutsche Nachricht")):
        listing = create_page(admin, "Notizie", layout="news_list", locale=locale)
        assert publish(admin, listing["id"]).status_code == 200
        item = admin.post(news, json={"title": title, "locale": locale}).get_json()["data"]
        body = {"version": 1, "title": title, "fields": {"date": "2026-10-26"}, "seo": {}}
        assert admin.put(f"{ENTRIES}/{item['id']}/draft", json=body).status_code == 200
        published = admin.post(f"{ENTRIES}/{item['id']}/publish", json={"draft_version": 2})
        assert published.status_code == 200
    widget = {"uid": "b" * 32, "type": "latest_entries", "data": {"title": "News"}}
    stored = admin.put(f"{API}/widgets/footer?locale=de", json={"version": 0, "items": [widget]})
    assert stored.status_code == 200
    html = visitor.get("/de/").get_data(as_text=True)
    assert "Deutsche Nachricht" in html and "Notizia italiana" not in html


# --- dalla review ---------------------------------------------------------------------------------


def _entry(client: FlaskClient, title: str, locale: str = "it") -> dict[str, Any]:
    news = f"{API}/collections/news/entries"
    item: dict[str, Any] = client.post(news, json={"title": title, "locale": locale}).get_json()[
        "data"
    ]
    body = {"version": 1, "title": title, "fields": {"date": "2026-10-26"}, "seo": {}}
    assert client.put(f"{ENTRIES}/{item['id']}/draft", json=body).status_code == 200
    return item


def _publish_entry(client: FlaskClient, entry_id: int, draft_version: int = 2) -> None:
    response = client.post(f"{ENTRIES}/{entry_id}/publish", json={"draft_version": draft_version})
    assert response.status_code == 200, response.get_json()


@pytest.mark.parametrize(("locale", "code"), [("it", "same_locale"), ("fr", "unknown_locale")])
def test_entry_translation_needs_another_active_language(
    admin: FlaskClient, locale: str, code: str
) -> None:
    item = _entry(admin, "Festa")
    response = admin.post(f"{ENTRIES}/{item['id']}/translations", json={"locale": locale})
    assert (response.status_code, error_code(response)) == (422, code)


def test_restoring_a_duplicate_entry_translation_is_refused(admin: FlaskClient) -> None:
    item = _entry(admin, "Festa")
    first = admin.post(f"{ENTRIES}/{item['id']}/translations", json={"locale": "de"})
    first_id = first.get_json()["data"]["id"]
    version = first.get_json()["data"]["version"]
    assert admin.delete(f"{ENTRIES}/{first_id}", json={"version": version}).status_code == 200
    again = admin.post(f"{ENTRIES}/{item['id']}/translations", json={"locale": "de"})
    assert again.status_code == 201
    back = admin.post(f"{ENTRIES}/{first_id}/restore", json={"version": version + 1})
    assert (back.status_code, error_code(back)) == (409, "translation_exists")


def test_a_failed_copy_leaves_no_half_translation(
    admin: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tutto o niente: se la copia non riesce, la lingua resta libera per riprovare."""
    from app.services import drafts

    page = create_page(admin, "Chi siamo")

    def broken(*_args: Any, **_kwargs: Any) -> int:
        raise RuntimeError("disco pieno")

    monkeypatch.setattr(drafts, "write", broken)
    with pytest.raises(RuntimeError):
        translate(admin, page["id"])
    monkeypatch.undo()
    listed = admin.get(f"{PAGES}/{page['id']}/translations").get_json()["data"]
    assert {row["locale"]: row["id"] for row in listed}["de"] is None
    assert translate(admin, page["id"]).status_code == 201


def test_two_translations_at_once_give_409(
    admin: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La seconda richiesta passa il controllo (simulato) ma l'indice unico la ferma: 409, non 500."""
    from app.services import entries, pages

    page = create_page(admin, "Chi siamo")
    item = _entry(admin, "Festa")
    assert translate(admin, page["id"]).status_code == 201
    first = admin.post(f"{ENTRIES}/{item['id']}/translations", json={"locale": "de"})
    assert first.status_code == 201
    monkeypatch.setattr(pages, "translation_taken", lambda *_a, **_k: False)
    monkeypatch.setattr(entries, "translation_taken", lambda *_a, **_k: False)
    again = translate(admin, page["id"])
    assert (again.status_code, error_code(again)) == (409, "translation_exists")
    other = admin.post(f"{ENTRIES}/{item['id']}/translations", json={"locale": "de"})
    assert (other.status_code, error_code(other)) == (409, "translation_exists")


@pytest.mark.parametrize(
    "path", ["/menus", "/widgets", "/collections", "/collections/news/entries"]
)
def test_unknown_panel_language_is_refused(admin: FlaskClient, path: str) -> None:
    response = admin.get(f"{API}{path}?locale=fr")
    assert (response.status_code, error_code(response)) == (422, "unknown_locale")


def test_entry_switcher_hreflang_and_sitemap(admin: FlaskClient, visitor: FlaskClient) -> None:
    it_home = home(admin)
    publish_translation(admin, it_home["id"], "Startseite")
    for locale in ("it", "de"):
        listing = create_page(admin, "Notizie", layout="news_list", locale=locale)
        assert publish(admin, listing["id"]).status_code == 200
    item = _entry(admin, "Festa")
    _publish_entry(admin, item["id"])
    html = visitor.get("/notizie/festa").get_data(as_text=True)
    assert 'hreflang="de" href="/de/"' in html  # non ancora tradotta: la homepage tedesca
    created = admin.post(f"{ENTRIES}/{item['id']}/translations", json={"locale": "de"})
    _publish_entry(admin, created.get_json()["data"]["id"])
    html = visitor.get("/notizie/festa").get_data(as_text=True)
    assert 'hreflang="de" href="/de/notizie/festa"' in html
    assert '<link rel="alternate" hreflang="de" href="http' in html
    sitemap = visitor.get("/sitemap.xml").get_data(as_text=True)
    assert 'hreflang="de" href="https://www.example.ch/de/notizie/festa"' in sitemap
