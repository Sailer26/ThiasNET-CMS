"""Anteprima della bozza e anteprima live (D-55, D-68): solo per chi entra nel pannello."""

from __future__ import annotations

import json
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import func, select

from app.extensions import db
from app.models.page import PageRevision
from app.services import page_cache
from tests.conftest import LoginAs
from tests.helpers import CSRF_HEADER, api_client
from tests.pages_helpers import create_page, doc, draft_version, put_draft, text_block, trash
from tests.render_fixtures import inspect


@pytest.fixture
def editor(login_as: LoginAs) -> FlaskClient:
    client, _ = login_as("editor")
    return client


@pytest.fixture
def page(editor: FlaskClient) -> dict[str, Any]:
    page = create_page(editor)
    zones = {"main": [text_block(1, "<p>Bozza salvata</p>")], "sidebar": []}
    assert put_draft(editor, page["id"], doc(zones=zones)).status_code == 200
    return page


def _post(client: FlaskClient, page_id: int, document: Any, raw: str | None = None) -> Any:
    body = raw if raw is not None else json.dumps(document)
    return client.post(f"/_preview/{page_id}", data={"document": body})


def _state(app: Flask, client: FlaskClient, page_id: int) -> tuple[int, int, int]:
    with app.app_context():
        revisions = db.session.execute(select(func.count()).select_from(PageRevision)).scalar_one()
        generation = page_cache.current_generation()
    return draft_version(client, page_id), revisions, generation


def test_saved_draft_is_visible_to_editors_only(
    app: Flask, editor: FlaskClient, page: dict[str, Any]
) -> None:
    response = editor.get(f"/_preview/{page['id']}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Bozza salvata" in html
    assert any("preview.js" in (s.get("src") or "") for s in inspect(html).find("script"))
    assert {"name": "robots", "content": "noindex"} in inspect(html).find("meta")
    assert api_client(app).get(f"/_preview/{page['id']}").status_code == 404
    assert app.test_client().get("/chi-siamo").status_code == 404  # mai pubblicata


def test_preview_headers_allow_only_same_origin_frames(
    editor: FlaskClient, page: dict[str, Any]
) -> None:
    headers = editor.get(f"/_preview/{page['id']}").headers
    assert headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "frame-ancestors 'self'" in headers["Content-Security-Policy"]
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Robots-Tag"] == "noindex"


def test_live_preview_renders_the_posted_document_without_writing(
    app: Flask, editor: FlaskClient, page: dict[str, Any]
) -> None:
    before = _state(app, editor, page["id"])
    zones = {
        "main": [text_block(1, "<p>Sto ancora scrivendo<script>x</script></p>")],
        "sidebar": [],
    }
    response = _post(editor, page["id"], doc(zones=zones))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Sto ancora scrivendo" in html and "<script>x" not in html
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert _state(app, editor, page["id"]) == before


def test_live_preview_needs_csrf(editor: FlaskClient, page: dict[str, Any]) -> None:
    editor.environ_base.pop(CSRF_HEADER)
    assert _post(editor, page["id"], doc()).status_code == 403


@pytest.mark.parametrize(
    "raw",
    [
        "non è json",
        json.dumps({"title": "x"}),
        '{"title": "x", "layout": "page", "seo": {}, "zones": {"main": [{"uid": "'
        + "a" * 32
        + '", "type": "map", "data": {"lat": NaN, "lng": 1}}]}}',
    ],
)
def test_invalid_document_is_422(editor: FlaskClient, page: dict[str, Any], raw: str) -> None:
    response = _post(editor, page["id"], None, raw=raw)
    assert response.status_code == 422
    assert response.mimetype == "text/html"


def test_anonymous_and_trashed_get_404(
    app: Flask, editor: FlaskClient, page: dict[str, Any]
) -> None:
    anonymous = api_client(app)
    assert _post(anonymous, page["id"], doc()).status_code == 404
    assert trash(editor, page["id"]).status_code == 200
    assert editor.get(f"/_preview/{page['id']}").status_code == 404


def test_contact_form_is_disabled_in_preview(editor: FlaskClient, page: dict[str, Any]) -> None:
    contacts = {
        "uid": "b" * 32,
        "type": "contacts",
        "data": {"title": "Scrivici", "show_form": True},
    }
    html = _post(editor, page["id"], doc(zones={"main": [contacts], "sidebar": []})).get_data(
        as_text=True
    )
    buttons = [a for _, a in inspect(html).tags if "disabled" in a]
    assert buttons
