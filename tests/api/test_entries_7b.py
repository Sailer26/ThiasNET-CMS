"""Notizie, parte del server per il pannello (Fase 7b): dati del sito, versioni, programmazione,
controllo prima di pubblicare, anteprima (D-135, D-40, D-42, D-55, D-156)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient

from tests.api.test_entries_api import ENTRIES, create, draft, fields, publish, save
from tests.conftest import LoginAs
from tests.helpers import API, error_code
from tests.pages_helpers import actions, create_page, put_draft, text_block
from tests.pages_helpers import publish as publish_page


@pytest.fixture
def admin(login_as: LoginAs) -> FlaskClient:
    client, _ = login_as("admin")
    return client


def listing(client: FlaskClient) -> dict[str, Any]:
    page = create_page(client, "Notizie", layout="news_list")
    assert publish_page(client, page["id"]).status_code == 200
    return page


def online(client: FlaskClient, title: str = "Festa", **extra: Any) -> dict[str, Any]:
    item = create(client, title)
    assert save(client, item["id"], title=title, **extra).status_code == 200
    assert publish(client, item["id"]).status_code == 200
    return item


def preview_post(client: FlaskClient, entry_id: int, document: dict[str, Any]) -> Any:
    return client.post(f"/_preview/entries/{entry_id}", data={"document": json.dumps(document)})


# --- dati del sito -------------------------------------------------------------------------


def test_site_lists_the_collections(admin: FlaskClient) -> None:
    site = admin.get(f"{API}/site").get_json()["data"]
    assert site["collections"] == [{"key": "news", "label": "Notizie"}]


# --- versioni ---------------------------------------------------------------------------------


def test_revisions_have_author_kind_and_content(admin: FlaskClient) -> None:
    item = online(admin)
    listed = admin.get(f"{ENTRIES}/{item['id']}/revisions").get_json()["data"]
    assert listed[0]["kind"] == "published" and listed[0]["author_name"]
    one = admin.get(f"{ENTRIES}/{item['id']}/revisions/{listed[0]['id']}")
    assert one.status_code == 200
    assert one.get_json()["data"]["snapshot"]["fields"]["date"] == "2026-10-24"
    assert admin.get(f"{ENTRIES}/{item['id']}/revisions/999999").status_code == 404


def test_restore_puts_a_revision_back_in_the_draft_only(app: Flask, admin: FlaskClient) -> None:
    item = online(admin, "Prima")
    first = admin.get(f"{ENTRIES}/{item['id']}/revisions").get_json()["data"][0]
    assert save(admin, item["id"], title="Seconda").status_code == 200
    version = draft(admin, item["id"])["version"]
    url = f"{ENTRIES}/{item['id']}/revisions/{first['id']}/restore"
    restored = admin.post(url, json={"draft_version": version})
    assert restored.status_code == 200, restored.get_json()
    assert draft(admin, item["id"])["data"]["title"] == "Prima"
    assert admin.get(f"{ENTRIES}/{item['id']}").get_json()["data"]["title"] == "Prima"  # online
    kinds = [r["kind"] for r in admin.get(f"{ENTRIES}/{item['id']}/revisions").get_json()["data"]]
    assert kinds[0] == "draft"  # la bozza "Seconda" non va persa (D-40)
    assert "entry.revision_restored" in actions(app)
    stale = admin.post(url, json={"draft_version": version})
    assert (stale.status_code, error_code(stale)) == (409, "version_conflict")


def test_editor_can_restore_into_the_draft(login_as: LoginAs) -> None:
    admin, _ = login_as("admin")
    item = online(admin)
    first = admin.get(f"{ENTRIES}/{item['id']}/revisions").get_json()["data"][0]
    editor, _ = login_as("editor")
    url = f"{ENTRIES}/{item['id']}/revisions/{first['id']}/restore"
    assert editor.post(url, json={"draft_version": 0}).status_code == 200


# --- programmazione --------------------------------------------------------------------------


def test_schedule_info_says_when_the_draft_is_newer(admin: FlaskClient) -> None:
    item = create(admin)
    assert save(admin, item["id"]).status_code == 200
    when = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    version = draft(admin, item["id"])["version"]
    sent = admin.post(
        f"{ENTRIES}/{item['id']}/schedule", json={"draft_version": version, "publish_at": when}
    )
    assert sent.status_code == 200
    info = admin.get(f"{ENTRIES}/{item['id']}").get_json()["data"]["schedule"]
    assert info["publish_at"] and info["author_name"] and info["draft_newer"] is False
    assert save(admin, item["id"], title="Cambiata dopo").status_code == 200
    info = admin.get(f"{ENTRIES}/{item['id']}").get_json()["data"]["schedule"]
    assert info["draft_newer"] is True
    assert (
        admin.get(f"{ENTRIES}/{create(admin, 'Altra')['id']}").get_json()["data"]["schedule"]
        is None
    )


# --- controllo prima di pubblicare -----------------------------------------------------------


def test_checks_block_like_publish_and_warn(admin: FlaskClient) -> None:
    listing(admin)
    other = online(admin, "Altra")
    item = create(admin)
    body = f'<p><a href="/notizie/{other["slug"]}">ok</a> <a href="/non-esiste">rotto</a></p>'
    assert save(admin, item["id"], fields={"body": body}).status_code == 200
    response = admin.get(f"{ENTRIES}/{item['id']}/checks")
    assert response.status_code == 200
    report = response.get_json()["data"]
    assert ("fields/date", "required") in {(e["path"], e["code"]) for e in report["blocking"]}
    warnings = {(w["path"], w["code"]) for w in report["warnings"]}
    assert ("seo/description", "seo_empty") in warnings
    assert ("fields/body", "link_broken") in warnings
    assert sum(1 for w in report["warnings"] if w["code"] == "link_broken") == 1


def test_page_links_to_entries_are_not_broken(admin: FlaskClient) -> None:
    listing(admin)
    news = online(admin, "Festa")
    page = create_page(admin, "Chi siamo")
    link = f'<p><a href="/notizie/{news["slug"]}">festa</a></p>'
    zones = {"main": [text_block(1, link)], "sidebar": []}
    document = {"title": "Chi siamo", "layout": "page", "seo": {}, "zones": zones}
    assert put_draft(admin, page["id"], document).status_code == 200
    report = admin.get(f"{API}/pages/{page['id']}/checks").get_json()["data"]
    assert not any(w["code"] == "link_broken" for w in report["warnings"])


# --- anteprima ----------------------------------------------------------------------------


def test_preview_shows_the_draft_without_writing(admin: FlaskClient) -> None:
    listing(admin)
    item = create(admin)
    assert save(admin, item["id"], title="Bozza segreta").status_code == 200
    before = draft(admin, item["id"])["version"]
    response = admin.get(f"/_preview/entries/{item['id']}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Bozza segreta" in html and 'name="robots" content="noindex"' in html
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["Cache-Control"] == "no-store"
    document = {
        "title": "Prova {{ 7*7 }}",
        "fields": fields(body="<p>{% include 'x' %}</p>"),
        "seo": {},
    }
    sent = preview_post(admin, item["id"], document)
    assert sent.status_code == 200
    assert "Prova {{ 7*7 }}" in sent.get_data(as_text=True)
    assert draft(admin, item["id"])["version"] == before  # niente scritture


def test_preview_rejects_unknown_fields(admin: FlaskClient) -> None:
    listing(admin)
    item = create(admin)
    document = {"title": "X", "fields": {"html": "<script>x</script>"}, "seo": {}}
    assert preview_post(admin, item["id"], document).status_code == 422


def test_preview_needs_a_listing_page(admin: FlaskClient) -> None:
    item = create(admin)
    response = admin.get(f"/_preview/entries/{item['id']}")
    assert response.status_code == 409
    assert "pagina che elenca" in response.get_data(as_text=True)


def test_preview_is_hidden_from_visitors(app: Flask, admin: FlaskClient) -> None:
    listing(admin)
    item = create(admin)
    assert app.test_client().get(f"/_preview/entries/{item['id']}").status_code == 404
    assert admin.get("/_preview/entries/999999").status_code == 404


# --- widget "ultime notizie" (D-155) ---------------------------------------------------------


def _latest_in_footer(client: FlaskClient, data: dict[str, Any]) -> Any:
    item = {"uid": "a" * 32, "type": "latest_entries", "data": data}
    return client.put(f"{API}/widgets/footer", json={"version": 0, "items": [item]})


def test_latest_entries_widget_shows_online_news(admin: FlaskClient) -> None:
    home = create_page(admin, "Home", slug="")
    assert publish_page(admin, home["id"]).status_code == 200
    assert _latest_in_footer(admin, {"title": "Dal Comune", "limit": 2}).status_code == 200
    assert "Dal Comune" not in admin.get("/").get_data(as_text=True)  # senza elenco: vuoto
    listing(admin)
    for title, day in (("Uno", "01"), ("Due", "02"), ("Tre", "03")):
        online(admin, title, fields=fields(date=f"2026-10-{day}"))
    admin.post(f"{API}/collections/news/entries", json={"title": "Solo bozza"})
    html = admin.get("/").get_data(as_text=True)
    assert "Dal Comune" in html and 'href="/notizie/tre"' in html and 'href="/notizie/due"' in html
    assert 'href="/notizie/uno"' not in html and "Solo bozza" not in html
    assert "3 ottobre 2026" in html
