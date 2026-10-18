"""Versioni e programmazione nell'editor (5c-1, D-121, D-122)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from flask.testing import FlaskClient

from tests.conftest import LoginAs
from tests.pages_helpers import PAGES, create_page, doc, publish, put_draft, text_block


def _published_page(client: FlaskClient) -> dict[str, Any]:
    page = create_page(client, "Chi siamo")
    put_draft(
        client, page["id"], doc(title="Chi siamo", zones={"main": [text_block(1)], "sidebar": []})
    )
    assert publish(client, page["id"]).status_code == 200
    return page


def test_revisions_carry_author_name_and_title(login_as: LoginAs) -> None:
    owner, _ = login_as("owner")
    editor, editor_user = login_as("editor", can_publish=True)
    page = _published_page(owner)
    put_draft(
        editor,
        page["id"],
        doc(title="Chi siamo noi", zones={"main": [text_block(1)], "sidebar": []}),
    )
    assert publish(editor, page["id"]).status_code == 200
    items = editor.get(f"{PAGES}/{page['id']}/revisions").get_json()["data"]
    assert [(r["author_name"], r["title"]) for r in items] == [
        (editor_user.email, "Chi siamo noi"),
        ("ThiasNET (assistenza)", "Chi siamo"),
    ]


def _schedule(client: FlaskClient, page_id: int) -> None:
    when = (datetime.now(UTC) + timedelta(days=2)).replace(microsecond=0).isoformat()
    draft = client.get(f"{PAGES}/{page_id}/draft").get_json()["data"]["version"]
    response = client.post(
        f"{PAGES}/{page_id}/schedule", json={"draft_version": draft, "publish_at": when}
    )
    assert response.status_code == 200, response.get_json()


def test_page_says_when_the_draft_changed_after_scheduling(login_as: LoginAs) -> None:
    admin, admin_user = login_as("admin")
    page = create_page(admin, "Eventi")
    put_draft(
        admin, page["id"], doc(title="Eventi", zones={"main": [text_block(1)], "sidebar": []})
    )
    assert admin.get(f"{PAGES}/{page['id']}").get_json()["data"]["schedule"] is None
    _schedule(admin, page["id"])
    schedule = admin.get(f"{PAGES}/{page['id']}").get_json()["data"]["schedule"]
    assert schedule["author_name"] == admin_user.email
    assert schedule["draft_newer"] is False
    assert schedule["publish_at"].endswith("+00:00")
    put_draft(
        admin, page["id"], doc(title="Eventi 2026", zones={"main": [text_block(1)], "sidebar": []})
    )
    assert admin.get(f"{PAGES}/{page['id']}").get_json()["data"]["schedule"]["draft_newer"] is True
