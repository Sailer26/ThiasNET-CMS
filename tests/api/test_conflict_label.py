"""Il 409 dice chi ha salvato (D-92), anche a un editor che non può leggere gli utenti."""

from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.services.errors import version_conflict
from tests.api.test_media_api import MEDIA, uploaded
from tests.conftest import LoginAs
from tests.pages_helpers import PAGES, create_page


def _conflict(client: FlaskClient, page_id: int) -> dict[str, object]:
    response = client.patch(f"{PAGES}/{page_id}", json={"version": 999, "slug": "altro"})
    assert response.status_code == 409
    details: dict[str, object] = response.get_json()["error"]["details"]
    return details


def test_editor_sees_who_saved_the_page(login_as: LoginAs) -> None:
    admin, admin_user = login_as("admin")
    editor, _ = login_as("editor")
    page = create_page(admin, "Chi siamo")
    assert _conflict(editor, page["id"])["updated_by_name"] == admin_user.email


def test_owner_is_shown_as_support(login_as: LoginAs) -> None:
    owner, _ = login_as("owner")
    editor, _ = login_as("editor")
    page = create_page(owner, "Servizi")
    assert _conflict(editor, page["id"])["updated_by_name"] == "ThiasNET (assistenza)"


def test_media_conflict_has_the_name_too(login_as: LoginAs) -> None:
    editor, editor_user = login_as("editor")
    media = uploaded(editor)
    response = editor.patch(f"{MEDIA}/{media['id']}", json={"version": 7, "alt": "x"})
    assert response.get_json()["error"]["details"]["updated_by_name"] == editor_user.email


@pytest.mark.parametrize("user_id", [None, 424242])
def test_unknown_author(app: Flask, user_id: int | None) -> None:
    with app.app_context():
        assert version_conflict(3, user_id, None).details["updated_by_name"] == "un altro utente"
