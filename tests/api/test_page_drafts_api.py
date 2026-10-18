"""Bozze con autosave e blocco ottimistico, operazioni sui singoli blocchi (D-07, D-39, D-44)."""

from __future__ import annotations

import time
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import select

from app.extensions import db
from app.models.page import Block, Page
from tests.conftest import LoginAs
from tests.helpers import error_code
from tests.pages_helpers import (
    PAGES,
    actions,
    create_page,
    details,
    doc,
    draft_version,
    get_draft,
    heading_block,
    publish,
    put_draft,
    text_block,
    trash,
    uid,
)
from tests.security.test_richtext_xss import ATTACKS


@pytest.fixture
def editor(login_as: LoginAs) -> FlaskClient:
    client, _ = login_as("editor")
    return client


@pytest.fixture
def page(editor: FlaskClient) -> dict[str, Any]:
    return create_page(editor)


def _blocks_url(page: dict[str, Any], suffix: str = "") -> str:
    return f"{PAGES}/{page['id']}/draft/blocks{suffix}"


def _published_blocks(app: Flask, page_id: int) -> list[tuple[str, str, str]]:
    with app.app_context():
        rows = db.session.execute(
            select(Block).where(Block.page_id == page_id).order_by(Block.zone, Block.sort)
        ).scalars()
        return [(b.zone, b.uid, b.type) for b in rows]


# --- Documento intero -------------------------------------------------------------


def test_put_draft_saves_cleaned_document(editor: FlaskClient, page: dict[str, Any]) -> None:
    body = doc(zones={"main": [text_block(1, "<p>Ciao<script>x</script></p>")], "sidebar": []})
    response = put_draft(editor, page["id"], body)
    assert response.status_code == 200
    assert response.get_json()["data"]["version"] == 2
    saved = get_draft(editor, page["id"])
    assert saved["version"] == 2
    assert saved["data"]["zones"]["main"][0]["data"]["body"] == "<p>Ciao</p>"


def test_autosave_never_touches_the_published_page(
    app: Flask, editor: FlaskClient, login_as: LoginAs
) -> None:
    publisher, _ = login_as("admin")
    page = create_page(publisher)
    put_draft(publisher, page["id"], doc(zones={"main": [text_block(1)], "sidebar": []}))
    assert publish(publisher, page["id"]).status_code == 200
    before = _published_blocks(app, page["id"])

    response = put_draft(editor, page["id"], doc(title="Nuovo", zones={"main": [], "sidebar": []}))
    assert response.status_code == 200
    assert _published_blocks(app, page["id"]) == before
    with app.app_context():
        stored = db.session.get_one(Page, page["id"])
        assert (stored.status, stored.title) == ("published", "Chi siamo")


def test_stale_draft_version_is_409(editor: FlaskClient, page: dict[str, Any]) -> None:
    assert put_draft(editor, page["id"], doc(), version=1).status_code == 200
    stale = put_draft(editor, page["id"], doc(title="Altro"), version=1)
    assert (stale.status_code, error_code(stale)) == (409, "version_conflict")
    assert stale.get_json()["error"]["details"]["current_version"] == 2


def test_draft_started_is_audited_once(app: Flask, login_as: LoginAs) -> None:
    client, _ = login_as("admin")
    page = create_page(client)
    assert publish(client, page["id"]).status_code == 200
    assert get_draft(client, page["id"]) | {"data": None} == {
        "version": 0,
        "data": None,
        "from_published": True,
        "author_id": None,
        "updated_at": None,
    }
    assert put_draft(client, page["id"], doc(), version=0).status_code == 200
    assert put_draft(client, page["id"], doc(title="Ancora"), version=1).status_code == 200
    assert put_draft(client, page["id"], doc(), version=0).status_code == 409
    assert actions(app).count("page.draft_started") == 1
    assert "page.draft_saved" not in actions(app)  # l'autosave non riempie l'audit


def test_invalid_document_is_422_with_details(editor: FlaskClient, page: dict[str, Any]) -> None:
    body = doc(zones={"main": [heading_block(1, "x" * 201)], "sidebar": [heading_block(2)]})
    response = put_draft(editor, page["id"], body)
    assert (response.status_code, error_code(response)) == (422, "invalid_content")
    assert details(response) == {
        ("zones/main/0/data/text", "maxLength"),
        ("zones/sidebar/0/type", "block_not_allowed"),
    }
    first = response.get_json()["error"]["details"][0]
    assert first["message"]


def test_missing_version_is_422(editor: FlaskClient, page: dict[str, Any]) -> None:
    response = editor.put(f"{PAGES}/{page['id']}/draft", json=doc())
    assert response.status_code == 422


def test_oversized_document_is_413(editor: FlaskClient, page: dict[str, Any]) -> None:
    blocks = [text_block(n, "<p>" + "x" * 9000 + "</p>") for n in range(1, 60)]
    response = put_draft(editor, page["id"], doc(zones={"main": blocks, "sidebar": []}))
    assert response.status_code == 413


def test_discard_draft_goes_back_to_published(app: Flask, login_as: LoginAs) -> None:
    client, _ = login_as("admin")
    page = create_page(client)
    put_draft(client, page["id"], doc(zones={"main": [text_block(1)], "sidebar": []}))
    publish(client, page["id"])
    put_draft(client, page["id"], doc(title="Prova", zones={"main": [], "sidebar": []}), version=0)
    response = client.delete(f"{PAGES}/{page['id']}/draft", json={"version": 1})
    assert response.status_code == 200
    draft = get_draft(client, page["id"])
    assert (draft["version"], draft["from_published"]) == (0, True)
    assert draft["data"]["title"] == "Chi siamo"
    assert [b["uid"] for b in draft["data"]["zones"]["main"]] == [uid(1)]
    assert "page.draft_discarded" in actions(app)


def test_discard_on_never_published_page_resets_to_empty(
    editor: FlaskClient, page: dict[str, Any]
) -> None:
    put_draft(editor, page["id"], doc(zones={"main": [text_block(1)], "sidebar": []}))
    assert editor.delete(f"{PAGES}/{page['id']}/draft", json={"version": 2}).status_code == 200
    draft = get_draft(editor, page["id"])
    assert draft["version"] == 0
    assert draft["data"]["zones"] == {"main": [], "sidebar": []}


def test_draft_of_trashed_page_is_404(editor: FlaskClient, page: dict[str, Any]) -> None:
    trash(editor, page["id"])
    assert editor.get(f"{PAGES}/{page['id']}/draft").status_code == 404
    assert put_draft(editor, page["id"], doc(), version=1).status_code == 404


# --- Singoli blocchi ----------------------------------------------------------------


def test_add_block_generates_uid_and_inserts_at_position(
    editor: FlaskClient, page: dict[str, Any]
) -> None:
    put_draft(
        editor, page["id"], doc(zones={"main": [text_block(1), text_block(2)], "sidebar": []})
    )
    response = editor.post(
        _blocks_url(page),
        json={
            "version": 2,
            "zone": "main",
            "type": "heading",
            "data": {"text": "Ciao"},
            "position": 1,
        },
    )
    assert response.status_code == 201
    body = response.get_json()["data"]
    assert body["version"] == 3
    new_uid = body["block"]["uid"]
    assert len(new_uid) == 32
    main = get_draft(editor, page["id"])["data"]["zones"]["main"]
    assert [b["uid"] for b in main] == [uid(1), new_uid, uid(2)]


def test_add_block_appends_by_default_and_validates(
    editor: FlaskClient, page: dict[str, Any]
) -> None:
    ok = editor.post(
        _blocks_url(page), json={"version": 1, "zone": "main", "type": "divider", "data": {}}
    )
    assert ok.status_code == 201
    hero = editor.post(
        _blocks_url(page), json={"version": 2, "zone": "main", "type": "hero", "data": {}}
    )
    assert (hero.status_code, error_code(hero)) == (422, "invalid_content")
    stale = editor.post(
        _blocks_url(page), json={"version": 1, "zone": "main", "type": "divider", "data": {}}
    )
    assert stale.status_code == 409


def test_update_and_delete_block(editor: FlaskClient, page: dict[str, Any]) -> None:
    put_draft(editor, page["id"], doc(zones={"main": [text_block(1)], "sidebar": []}))
    url = _blocks_url(page, f"/{uid(1)}")
    updated = editor.patch(url, json={"version": 2, "data": {"body": "<p>Nuovo</p>"}})
    assert updated.status_code == 200
    assert updated.get_json()["data"]["block"]["data"] == {"body": "<p>Nuovo</p>"}
    assert (
        editor.patch(_blocks_url(page, f"/{uid(9)}"), json={"version": 3, "data": {}}).status_code
        == 404
    )
    assert editor.delete(url, json={"version": 3}).status_code == 200
    assert get_draft(editor, page["id"])["data"]["zones"]["main"] == []
    assert editor.delete(url, json={"version": 4}).status_code == 404


def test_reorder_and_move_blocks_between_zones(editor: FlaskClient, page: dict[str, Any]) -> None:
    blocks = [text_block(1), heading_block(2), text_block(3)]
    put_draft(editor, page["id"], doc(zones={"main": blocks, "sidebar": []}))
    url = _blocks_url(page, "/reorder")
    moved = editor.post(
        url, json={"version": 2, "zones": {"main": [uid(2), uid(1)], "sidebar": [uid(3)]}}
    )
    assert moved.status_code == 200
    zones = get_draft(editor, page["id"])["data"]["zones"]
    assert [b["uid"] for b in zones["main"]] == [uid(2), uid(1)]
    assert [b["uid"] for b in zones["sidebar"]] == [uid(3)]

    missing = editor.post(
        url, json={"version": 3, "zones": {"main": [uid(2)], "sidebar": [uid(3)]}}
    )
    assert (missing.status_code, error_code(missing)) == (422, "reorder_mismatch")
    heading_in_sidebar = editor.post(
        url, json={"version": 3, "zones": {"main": [uid(1)], "sidebar": [uid(3), uid(2)]}}
    )
    assert (heading_in_sidebar.status_code, error_code(heading_in_sidebar)) == (
        422,
        "invalid_content",
    )


def test_duplicate_uid_in_document_is_422(editor: FlaskClient, page: dict[str, Any]) -> None:
    response = put_draft(editor, page["id"], doc(zones={"main": [text_block(1), text_block(1)]}))
    assert ("zones/main/1/uid", "duplicate_uid") in details(response)


# --- Sicurezza dei contenuti ----------------------------------------------------------


@pytest.mark.parametrize("attack", ATTACKS)
def test_xss_never_reaches_the_stored_draft(
    editor: FlaskClient, page: dict[str, Any], attack: str
) -> None:
    response = put_draft(
        editor, page["id"], doc(zones={"main": [text_block(1, attack)], "sidebar": []})
    )
    assert response.status_code == 200
    stored = str(get_draft(editor, page["id"])["data"]).lower()
    for marker in ("<script", "onerror", "javascript:", "<iframe", "<svg", "style="):
        assert marker not in stored


def test_plain_text_keeps_markup_literal(editor: FlaskClient, page: dict[str, Any]) -> None:
    quote = {"uid": uid(1), "type": "quote", "data": {"text": "<b>{{ 7*7 }}</b>"}}
    put_draft(editor, page["id"], doc(zones={"main": [quote], "sidebar": []}))
    stored = get_draft(editor, page["id"])["data"]["zones"]["main"][0]["data"]["text"]
    assert stored == "<b>{{ 7*7 }}</b>"


def test_draft_requires_login(app: Flask, page: dict[str, Any]) -> None:
    from tests.helpers import api_client

    assert api_client(app).get(f"{PAGES}/{page['id']}/draft").status_code == 401


def test_draft_version_helper_matches_api(editor: FlaskClient, page: dict[str, Any]) -> None:
    assert draft_version(editor, page["id"]) == 1


# --- Regressioni dalla review ECC della Fase 2 -------------------------------------------


def _raw_put(editor: FlaskClient, page: dict[str, Any], body: str) -> Any:
    return editor.put(f"{PAGES}/{page['id']}/draft", data=body, content_type="application/json")


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_are_rejected(
    editor: FlaskClient, page: dict[str, Any], value: str
) -> None:
    block = f'{{"uid": "{uid(1)}", "type": "map", "data": {{"lat": {value}, "lng": 8}}}}'
    body = (
        '{"version": 1, "title": "x", "layout": "page", "seo": {}, '
        f'"zones": {{"main": [{block}], "sidebar": []}}}}'
    )
    assert _raw_put(editor, page, body).status_code == 422


def test_deeply_nested_json_is_422_not_500(editor: FlaskClient, page: dict[str, Any]) -> None:
    assert _raw_put(editor, page, "[" * 50000 + "]" * 50000).status_code == 422


def test_uid_with_trailing_newline_is_rejected(editor: FlaskClient, page: dict[str, Any]) -> None:
    block = {**text_block(1), "uid": uid(1) + "\n"}
    response = put_draft(editor, page["id"], doc(zones={"main": [block], "sidebar": []}))
    assert response.status_code == 422


def test_huge_nested_richtext_is_rejected_before_sanitizing(
    editor: FlaskClient, page: dict[str, Any]
) -> None:
    start = time.perf_counter()
    nested = text_block(1, "<ul>" * 30000 + "<li>x")
    response = put_draft(editor, page["id"], doc(zones={"main": [nested], "sidebar": []}))
    assert ("zones/main/0/data/body", "maxLength") in details(response)
    assert time.perf_counter() - start < 2


def test_phone_links_with_spaces_are_kept(editor: FlaskClient, page: dict[str, Any]) -> None:
    rich = text_block(1, '<p><a href="tel:+41 91 123 45 67">Chiama</a></p>')
    cta = {
        "uid": uid(2),
        "type": "cta",
        "data": {"title": "x", "button_label": "Chiama", "url": "tel:+41 91 123 45 67"},
    }
    response = put_draft(editor, page["id"], doc(zones={"main": [rich, cta], "sidebar": []}))
    assert response.status_code == 200, response.get_json()
    main = get_draft(editor, page["id"])["data"]["zones"]["main"]
    assert 'href="tel:+41911234567"' in main[0]["data"]["body"]
    assert main[1]["data"]["url"] == "tel:+41911234567"
