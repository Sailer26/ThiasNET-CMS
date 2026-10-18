"""Libreria media via API (D-70 … D-85): upload, doppioni, limiti, ricerca, modifiche,
eliminazione protetta, sostituzione e cartelle."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.services import page_cache
from tests.conftest import LoginAs
from tests.helpers import API, error_code
from tests.media_fixtures import PDF_BYTES, image_bytes
from tests.pages_helpers import actions, create_page, doc, publish, put_draft, uid

MEDIA = f"{API}/media"
FOLDERS = f"{MEDIA}/folders"


def upload(client: FlaskClient, data: bytes, name: str = "foto.png", **form: Any) -> Any:
    body = {"file": (io.BytesIO(data), name), **form}
    return client.post(MEDIA, data=body, content_type="multipart/form-data")


def uploaded(
    client: FlaskClient, data: bytes | None = None, name: str = "foto.png", **form: Any
) -> dict[str, Any]:
    response = upload(
        client, data if data is not None else image_bytes(size=(800, 600)), name, **form
    )
    assert response.status_code == 201, response.get_json()
    result: dict[str, Any] = response.get_json()["data"]
    return result


def stored_files(app: Flask) -> set[str]:
    root = Path(app.config["MEDIA_ROOT"])
    return {p.name for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def editor(login_as: LoginAs) -> FlaskClient:
    client, _ = login_as("editor", can_publish=True)  # un editor abilitato a pubblicare
    return client


def _image_page(client: FlaskClient, media_id: int, publish_it: bool = True) -> dict[str, Any]:
    page = create_page(client, "Galleria")
    block = {"uid": uid(1), "type": "image", "data": {"media_id": media_id}}
    put_draft(client, page["id"], doc(title="Galleria", zones={"main": [block], "sidebar": []}))
    if publish_it:
        assert publish(client, page["id"]).status_code == 200
    return page


# --- Upload -------------------------------------------------------------------------


def test_upload_requires_login(api: Any) -> None:
    assert upload(api, image_bytes()).status_code == 401


def test_upload_image_creates_master_and_variants(app: Flask, editor: FlaskClient) -> None:
    media = uploaded(editor, name="Vacanze al lago.JPG")
    assert (media["kind"], media["width"], media["height"], media["alt"]) == ("image", 800, 600, "")
    assert media["name"] == "Vacanze al lago.JPG"
    assert media["url"].startswith(f"/media/{media['key']}/r1-master.")
    assert media["thumbnail_url"].endswith(".webp")
    assert {"card", "content", "thumb", "hero"} <= set(media["sizes"])
    assert "Vacanze" not in "".join(stored_files(app))  # mai il nome dell'utente su disco
    assert "media.uploaded" in actions(app)


def test_upload_pdf_has_a_stable_address(editor: FlaskClient) -> None:
    media = uploaded(editor, PDF_BYTES, "Regolamento.pdf")
    assert (media["kind"], media["url"]) == ("document", f"/media/{media['key']}/file.pdf")


@pytest.mark.parametrize(
    ("data", "name"),
    [
        (b"<html><script>alert(1)</script></html>", "foto.png"),
        (b'<svg xmlns="http://www.w3.org/2000/svg"><script>x</script></svg>', "logo.svg"),
        (b"PK" + bytes(30), "documento.docx"),
    ],
)
def test_unsupported_or_disguised_files_are_415(
    editor: FlaskClient, data: bytes, name: str
) -> None:
    response = upload(editor, data, name)
    assert (response.status_code, error_code(response)) == (415, "unsupported_type")


def test_empty_or_missing_file_is_422(editor: FlaskClient) -> None:
    assert upload(editor, b"", "vuoto.png").status_code == 422
    assert editor.post(MEDIA, data={}, content_type="multipart/form-data").status_code == 422


def test_duplicates_return_the_existing_media(editor: FlaskClient) -> None:
    data = image_bytes(size=(50, 50))
    first = uploaded(editor, data)
    again = upload(editor, data, "copia.png")
    assert again.status_code == 200
    assert again.get_json()["data"]["id"] == first["id"]
    assert again.get_json()["meta"] == {"duplicate": True}


def test_quota_and_size_limits(app: Flask, editor: FlaskClient) -> None:
    app.config["MEDIA_QUOTA_MB"] = 0
    full = upload(editor, image_bytes())
    assert (full.status_code, error_code(full)) == (507, "storage_full")
    app.config["MEDIA_QUOTA_MB"] = 10
    app.config["MAX_CONTENT_LENGTH"] = 500
    assert upload(editor, image_bytes(size=(400, 400), color=(1, 2, 3))).status_code == 413


def test_too_many_pixels_is_422(app: Flask, editor: FlaskClient) -> None:
    app.config["MEDIA_MAX_PIXELS"] = 1000
    response = upload(editor, image_bytes(size=(100, 100)))
    assert (response.status_code, error_code(response)) == (422, "invalid_image")


# --- Elenco, ricerca e modifiche ------------------------------------------------------------


def test_search_ignores_case_and_accents_and_filters(editor: FlaskClient) -> None:
    city = uploaded(editor, image_bytes(color=(1, 1, 1)), "Città vecchia.png")
    uploaded(editor, image_bytes(color=(2, 2, 2)), "mare.png", alt="Spiaggia")
    pdf = uploaded(editor, PDF_BYTES, "orari.pdf")
    assert [m["id"] for m in editor.get(f"{MEDIA}?q=CITTA").get_json()["data"]] == [city["id"]]
    assert len(editor.get(f"{MEDIA}?q=spiaggia").get_json()["data"]) == 1
    assert [m["id"] for m in editor.get(f"{MEDIA}?kind=document").get_json()["data"]] == [pdf["id"]]
    missing = editor.get(f"{MEDIA}?missing_alt=1").get_json()["data"]
    assert {m["id"] for m in missing} == {city["id"]}
    body = editor.get(f"{MEDIA}?limit=2").get_json()
    assert body["meta"]["total"] == 3 and len(body["data"]) == 2


def test_update_alt_name_and_focal_point(app: Flask, editor: FlaskClient) -> None:
    media = uploaded(editor)
    old_files = stored_files(app)
    before = _generation(app)
    response = editor.patch(
        f"{MEDIA}/{media['id']}",
        json={
            "version": 1,
            "alt": "  Lago al tramonto ",
            "name": "Lago",
            "focal_x": 0,
            "focal_y": 100,
        },
    )
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert (data["alt"], data["name"], data["focal_x"], data["version"], data["file_rev"]) == (
        "Lago al tramonto",
        "Lago",
        0,
        2,
        2,
    )
    assert not old_files & stored_files(app)  # varianti rifatte, quelle vecchie cancellate
    assert _generation(app) > before
    stale = editor.patch(f"{MEDIA}/{media['id']}", json={"version": 1, "alt": "x"})
    assert (stale.status_code, error_code(stale)) == (409, "version_conflict")


def test_alt_cannot_be_removed_from_an_image_online(editor: FlaskClient) -> None:
    media = uploaded(editor, alt="Lago")
    _image_page(editor, media["id"])
    response = editor.patch(f"{MEDIA}/{media['id']}", json={"version": 1, "alt": " "})
    assert (response.status_code, error_code(response)) == (422, "alt_required")


# --- Eliminazione protetta -----------------------------------------------------------------


def test_unused_media_can_be_deleted_also_by_editors(app: Flask, editor: FlaskClient) -> None:
    media = uploaded(editor)
    assert editor.delete(f"{MEDIA}/{media['id']}", json={"version": 1}).status_code == 200
    assert stored_files(app) == set()
    assert editor.get(f"{MEDIA}/{media['id']}").status_code == 404
    assert "media.deleted" in actions(app)


def test_media_in_use_cannot_be_deleted(editor: FlaskClient) -> None:
    online = uploaded(editor, image_bytes(color=(9, 9, 9)), alt="A")
    in_draft = uploaded(editor, image_bytes(color=(8, 8, 8)))
    social = uploaded(editor, image_bytes(color=(7, 7, 7)), alt="B")
    _image_page(editor, online["id"])
    _image_page(editor, in_draft["id"], publish_it=False)
    page = create_page(editor, "Social")
    put_draft(editor, page["id"], doc(title="Social", seo={"og_image_media_id": social["id"]}))
    for media, where in ((online, "published"), (in_draft, "draft"), (social, "draft")):
        response = editor.delete(f"{MEDIA}/{media['id']}", json={"version": 1})
        assert (response.status_code, error_code(response)) == (409, "media_in_use")
        assert where in {d["where"] for d in response.get_json()["error"]["details"]}
    detail = editor.get(f"{MEDIA}/{online['id']}").get_json()["data"]
    assert detail["used_by"][0]["title"] == "Galleria"


# --- Sostituzione (D-85) ------------------------------------------------------------------


def _replace(client: FlaskClient, media_id: int, data: bytes, name: str, version: int = 1) -> Any:
    body = {"file": (io.BytesIO(data), name), "version": str(version)}
    return client.post(f"{MEDIA}/{media_id}/file", data=body, content_type="multipart/form-data")


def test_replace_image_keeps_the_media(app: Flask, editor: FlaskClient) -> None:
    media = uploaded(editor)
    response = _replace(
        editor, media["id"], image_bytes(size=(300, 200), color=(0, 90, 0)), "nuova.png"
    )
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert (data["id"], data["file_rev"], data["width"]) == (media["id"], 2, 300)
    assert data["url"] != media["url"]
    assert all(name.startswith("r2") for name in stored_files(app))
    assert "media.file_replaced" in actions(app)


def test_replace_pdf_keeps_the_address(editor: FlaskClient) -> None:
    media = uploaded(editor, PDF_BYTES, "orari.pdf")
    response = _replace(editor, media["id"], PDF_BYTES + b"%v2\n", "orari-2027.pdf")
    assert response.get_json()["data"]["url"] == media["url"]


def test_replace_rules(editor: FlaskClient) -> None:
    image = uploaded(editor, image_bytes(color=(1, 2, 3)))
    other = uploaded(editor, image_bytes(color=(4, 5, 6)))
    wrong_kind = _replace(editor, image["id"], PDF_BYTES, "x.pdf")
    assert (wrong_kind.status_code, error_code(wrong_kind)) == (422, "kind_mismatch")
    duplicate = _replace(editor, image["id"], image_bytes(color=(4, 5, 6)), "x.png")
    assert (duplicate.status_code, error_code(duplicate)) == (409, "duplicate")
    assert other["id"] != image["id"]


# --- Cartelle (D-82) --------------------------------------------------------------------


def _folder(client: FlaskClient, name: str, parent_id: int | None = None) -> Any:
    return client.post(FOLDERS, json={"name": name, "parent_id": parent_id})


def test_folders(editor: FlaskClient) -> None:
    events = _folder(editor, "Eventi").get_json()["data"]
    year = _folder(editor, "2026", events["id"]).get_json()["data"]
    month = _folder(editor, "Ottobre", year["id"]).get_json()["data"]
    too_deep = _folder(editor, "Giorno", month["id"])
    assert (too_deep.status_code, error_code(too_deep)) == (422, "folder_too_deep")
    duplicate = _folder(editor, "EVENTÌ")
    assert (duplicate.status_code, error_code(duplicate)) == (409, "folder_exists")
    cycle = editor.patch(f"{FOLDERS}/{events['id']}", json={"parent_id": year["id"]})
    assert (cycle.status_code, error_code(cycle)) == (422, "folder_cycle")
    media = uploaded(editor, folder_id=str(year["id"]))
    assert [m["id"] for m in editor.get(f"{MEDIA}?folder_id={year['id']}").get_json()["data"]] == [
        media["id"]
    ]
    not_empty = editor.delete(f"{FOLDERS}/{year['id']}")
    assert (not_empty.status_code, error_code(not_empty)) == (409, "folder_not_empty")
    assert editor.delete(f"{FOLDERS}/{month['id']}").status_code == 200
    tree = editor.get(FOLDERS).get_json()["data"]
    assert tree[0]["name"] == "Eventi" and tree[0]["children"][0]["name"] == "2026"


def _generation(app: Flask) -> int:
    with app.app_context():
        return page_cache.current_generation()
