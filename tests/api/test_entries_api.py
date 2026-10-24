"""Notizie (Fase 7a, D-147 … D-149): bozza, pubblica, programma, ritira, cestino, versioni."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

from tests.conftest import LoginAs
from tests.helpers import API, error_code
from tests.pages_helpers import actions

NEWS = f"{API}/collections/news/entries"
ENTRIES = f"{API}/entries"


@pytest.fixture
def admin(login_as: LoginAs) -> FlaskClient:
    client, _ = login_as("admin")
    return client


def create(client: FlaskClient, title: str = "Festa del paese", **extra: Any) -> dict[str, Any]:
    response = client.post(NEWS, json={"title": title, **extra})
    assert response.status_code == 201, response.get_json()
    data: dict[str, Any] = response.get_json()["data"]
    return data


def draft(client: FlaskClient, entry_id: int) -> dict[str, Any]:
    response = client.get(f"{ENTRIES}/{entry_id}/draft")
    assert response.status_code == 200, response.get_json()
    data: dict[str, Any] = response.get_json()["data"]
    return data


def fields(**extra: Any) -> dict[str, Any]:
    return {"date": "2026-10-24", "summary": "Tutti in piazza", "body": "<p>Ciao</p>", **extra}


def save(
    client: FlaskClient, entry_id: int, version: int | None = None, **body: Any
) -> TestResponse:
    known = draft(client, entry_id)["version"] if version is None else version
    document = {"title": "Festa del paese", "fields": fields(), "seo": {}, **body}
    return client.put(f"{ENTRIES}/{entry_id}/draft", json={"version": known, **document})


def publish(client: FlaskClient, entry_id: int) -> TestResponse:
    version = draft(client, entry_id)["version"]
    return client.post(f"{ENTRIES}/{entry_id}/publish", json={"draft_version": version})


def entry(client: FlaskClient, entry_id: int) -> dict[str, Any]:
    data: dict[str, Any] = client.get(f"{ENTRIES}/{entry_id}").get_json()["data"]
    return data


def details(response: TestResponse) -> set[tuple[str, str]]:
    found = (response.get_json() or {}).get("error", {}).get("details") or []
    return {(d["path"], d["code"]) for d in found}


def test_collections_list_the_theme_collections(admin: FlaskClient) -> None:
    response = admin.get(f"{API}/collections")
    assert response.status_code == 200
    found = {c["key"]: c for c in response.get_json()["data"]}
    assert set(found) == {"news"}
    news = found["news"]
    assert news["label"] == "Notizie" and news["listing"] is None
    schema = news["schema"]
    assert schema["properties"]["body"]["x-richtext"] is True
    assert schema["properties"]["cover"]["x-media"] == "image"
    assert schema["properties"]["date"]["title"] == "Data"
    assert schema["required"] == ["date"]
    assert admin.get(f"{API}/collections/eventi/entries").status_code == 404


def test_create_gives_a_free_slug_and_an_empty_draft(app: Flask, admin: FlaskClient) -> None:
    first = create(admin)
    second = create(admin)
    assert (first["slug"], second["slug"]) == ("festa-del-paese", "festa-del-paese-2")
    assert first["status"] == "draft" and first["locale"] == "it" and first["collection"] == "news"
    working = draft(admin, first["id"])
    assert working["version"] == 1
    assert working["data"] == {"title": "Festa del paese", "fields": {}, "seo": {}}
    assert "entry.created" in actions(app)
    assert admin.post(NEWS, json={"title": "  "}).status_code == 422


def test_draft_is_cleaned_and_lenient_publish_is_strict(admin: FlaskClient) -> None:
    item = create(admin)
    loose = save(admin, item["id"], fields={"summary": "  Solo testo "})
    assert loose.status_code == 200, loose.get_json()  # in bozza la data può mancare (D-46)
    stored = draft(admin, item["id"])["data"]["fields"]
    assert stored == {"summary": "Solo testo"}
    response = publish(admin, item["id"])
    assert response.status_code == 422
    assert ("fields/date", "required") in details(response)


@pytest.mark.parametrize(
    ("body", "problem"),
    [
        ({"fields": fields(html="<script>x</script>")}, ("fields/html", "additionalProperties")),
        ({"fields": fields(date="24.10.2026")}, ("fields/date", "invalid_date")),
        ({"fields": fields(date="2026-02-31")}, ("fields/date", "invalid_date")),
        ({"fields": fields(summary="x" * 301)}, ("fields/summary", "maxLength")),
        ({"fields": fields(cover="1")}, ("fields/cover", "type")),
        ({"seo": {"custom_css": "body{}"}}, ("seo/custom_css", "additionalProperties")),
    ],
)
def test_draft_validation(
    admin: FlaskClient, body: dict[str, Any], problem: tuple[str, str]
) -> None:
    item = create(admin)
    response = save(admin, item["id"], **body)
    assert response.status_code == 422, response.get_json()
    assert problem in details(response)


def test_rich_text_keeps_only_the_allowlist(admin: FlaskClient) -> None:
    item = create(admin)
    body = '<p onclick="x()">Ciao <script>alert(1)</script><strong>tutti</strong></p>'
    assert save(admin, item["id"], fields=fields(body=body)).status_code == 200
    stored = draft(admin, item["id"])["data"]["fields"]["body"]
    assert "<strong>tutti</strong>" in stored and "script" not in stored and "onclick" not in stored


def test_publish_moves_the_draft_online(app: Flask, admin: FlaskClient) -> None:
    item = create(admin)
    assert save(admin, item["id"], title="Festa  del paese ").status_code == 200
    response = publish(admin, item["id"])
    assert response.status_code == 200, response.get_json()
    online = entry(admin, item["id"])
    assert online["status"] == "published" and online["published_at"] and not online["has_draft"]
    assert online["title"] == "Festa del paese"
    assert draft(admin, item["id"])["from_published"] is True
    assert "entry.published" in actions(app)
    revisions = admin.get(f"{ENTRIES}/{item['id']}/revisions").get_json()["data"]
    assert len(revisions) == 1 and revisions[0]["title"] == "Festa del paese"
    again = publish(admin, item["id"])
    assert (again.status_code, error_code(again)) == (409, "no_draft")


def test_version_conflict_on_draft(admin: FlaskClient) -> None:
    item = create(admin)
    assert save(admin, item["id"], version=1).status_code == 200
    stale = save(admin, item["id"], version=1)
    assert (stale.status_code, error_code(stale)) == (409, "version_conflict")


def test_schedule_and_unschedule(admin: FlaskClient) -> None:
    item = create(admin)
    assert save(admin, item["id"]).status_code == 200
    when = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    version = draft(admin, item["id"])["version"]
    response = admin.post(
        f"{ENTRIES}/{item['id']}/schedule", json={"draft_version": version, "publish_at": when}
    )
    assert response.status_code == 200, response.get_json()
    scheduled = entry(admin, item["id"])
    assert scheduled["status"] == "scheduled" and scheduled["publish_at"]
    off = admin.post(f"{ENTRIES}/{item['id']}/unschedule", json={"version": scheduled["version"]})
    assert off.status_code == 200
    assert entry(admin, item["id"])["status"] == "draft"
    past = admin.post(
        f"{ENTRIES}/{item['id']}/schedule",
        json={
            "draft_version": draft(admin, item["id"])["version"],
            "publish_at": "2020-01-01T08:00:00+01:00",
        },
    )
    assert (past.status_code, error_code(past)) == (422, "invalid_publish_at")


def test_due_schedule_publishes_from_the_command(app: Flask, admin: FlaskClient) -> None:
    from app.services import entry_publishing

    item = create(admin)
    assert save(admin, item["id"]).status_code == 200
    when = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    version = draft(admin, item["id"])["version"]
    sent = admin.post(
        f"{ENTRIES}/{item['id']}/schedule", json={"draft_version": version, "publish_at": when}
    )
    assert sent.status_code == 200
    with app.app_context():
        result = entry_publishing.run_due(datetime.now(UTC) + timedelta(minutes=10))
    assert (result.published, result.failed) == (1, 0)
    assert entry(admin, item["id"])["status"] == "published"


def test_schedule_that_no_longer_validates_is_dropped(app: Flask, admin: FlaskClient) -> None:
    """Il tema o i media cambiano dopo la programmazione: niente pubblicazione, niente
    tentativi ogni minuto, e il registro dice perché."""
    from app.extensions import db
    from app.models.entry import Entry
    from app.services import entry_publishing

    item = create(admin)
    assert save(admin, item["id"], fields=fields(cover=999_999)).status_code == 200
    with app.app_context():  # programmata quando l'immagine c'era ancora
        stored = db.session.get_one(Entry, item["id"])
        stored.scheduled_json = {"title": "Festa", "fields": fields(cover=999_999), "seo": {}}
        stored.publish_at = datetime.now(UTC) - timedelta(minutes=1)
        stored.status = "scheduled"
        db.session.commit()
        result = entry_publishing.run_due(datetime.now(UTC))
    assert (result.published, result.failed) == (0, 0)
    after = entry(admin, item["id"])
    assert (after["status"], after["publish_at"]) == ("draft", None)
    assert "entry.schedule_failed" in actions(app)


def test_publish_checks_the_media(admin: FlaskClient) -> None:
    item = create(admin)
    assert save(admin, item["id"], fields=fields(cover=999_999)).status_code == 200
    response = publish(admin, item["id"])
    assert response.status_code == 422
    assert ("fields/cover", "media_missing") in details(response)


def test_empty_date_counts_as_missing(admin: FlaskClient) -> None:
    item = create(admin)
    assert save(admin, item["id"], fields=fields(date="")).status_code == 200
    assert "date" not in draft(admin, item["id"])["data"]["fields"]
    response = publish(admin, item["id"])
    assert ("fields/date", "required") in details(response)


def test_two_creations_with_the_same_slug_give_a_conflict(
    admin: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import entries

    create(admin)
    monkeypatch.setattr(entries, "_free_slug", lambda *_args: "festa-del-paese")
    response = admin.post(NEWS, json={"title": "Festa del paese"})
    assert (response.status_code, error_code(response)) == (409, "slug_taken")


def test_unpublish_and_trash_and_restore(admin: FlaskClient) -> None:
    item = create(admin)
    save(admin, item["id"])
    assert publish(admin, item["id"]).status_code == 200
    online = entry(admin, item["id"])
    off = admin.post(f"{ENTRIES}/{item['id']}/unpublish", json={"version": online["version"]})
    assert off.status_code == 200
    assert entry(admin, item["id"])["status"] == "draft"
    current = entry(admin, item["id"])["version"]
    trashed = admin.delete(f"{ENTRIES}/{item['id']}", json={"version": current})
    assert trashed.status_code == 200
    assert admin.get(f"{ENTRIES}/{item['id']}").status_code == 404
    listed = admin.get(NEWS).get_json()["data"]
    assert all(e["id"] != item["id"] for e in listed)
    trash = admin.get(f"{NEWS}?trash=1").get_json()["data"]
    assert [e["id"] for e in trash] == [item["id"]]
    back = admin.post(f"{ENTRIES}/{item['id']}/restore", json={"version": trash[0]["version"]})
    assert back.status_code == 200, back.get_json()
    assert entry(admin, item["id"])["status"] == "draft"


def test_restore_with_a_taken_slug_is_refused(admin: FlaskClient) -> None:
    first = create(admin)
    admin.delete(f"{ENTRIES}/{first['id']}", json={"version": first["version"]})
    create(admin)  # prende lo stesso indirizzo
    trashed = admin.get(f"{NEWS}?trash=1").get_json()["data"][0]
    response = admin.post(f"{ENTRIES}/{first['id']}/restore", json={"version": trashed["version"]})
    assert (response.status_code, error_code(response)) == (409, "slug_taken")


def test_slug_can_change_only_before_the_first_publication(admin: FlaskClient) -> None:
    """D-152: l'indirizzo di una notizia già uscita non cambia (nessun link rotto)."""
    item = create(admin)
    url = f"{ENTRIES}/{item['id']}"
    changed = admin.patch(url, json={"version": item["version"], "slug": "festa-2026"})
    assert changed.status_code == 200, changed.get_json()
    assert entry(admin, item["id"])["slug"] == "festa-2026"
    bad = admin.patch(url, json={"version": entry(admin, item["id"])["version"], "slug": "Festa!"})
    assert bad.status_code == 422
    save(admin, item["id"])
    assert publish(admin, item["id"]).status_code == 200
    fixed = admin.patch(url, json={"version": entry(admin, item["id"])["version"], "slug": "altro"})
    assert (fixed.status_code, error_code(fixed)) == (409, "slug_fixed")


def test_editor_writes_drafts_but_cannot_publish(login_as: LoginAs) -> None:
    editor, _ = login_as("editor")
    item = create(editor)
    assert save(editor, item["id"]).status_code == 200
    assert publish(editor, item["id"]).status_code == 403


def test_editor_cannot_touch_online_entries(login_as: LoginAs) -> None:
    admin, _ = login_as("admin")
    item = create(admin)
    save(admin, item["id"])
    assert publish(admin, item["id"]).status_code == 200
    editor, _ = login_as("editor")
    online = entry(editor, item["id"])
    trashed = editor.delete(f"{ENTRIES}/{item['id']}", json={"version": online["version"]})
    assert trashed.status_code == 403


def test_listing_in_the_panel_is_paginated(admin: FlaskClient) -> None:
    for n in range(3):
        create(admin, f"Notizia {n}")
    response = admin.get(f"{NEWS}?limit=2&page=2")
    assert response.status_code == 200
    body = response.get_json()
    assert len(body["data"]) == 1 and body["meta"]["total"] == 3 and body["meta"]["pages"] == 2
    assert admin.get(f"{NEWS}?page=0").status_code == 422
