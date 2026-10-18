"""Pagina Media del pannello (5c-1): spazio usato, file senza cartella, conteggi (D-117, D-120)."""

from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from tests.api.test_media_api import FOLDERS, MEDIA, uploaded
from tests.conftest import LoginAs
from tests.media_fixtures import PDF_BYTES, image_bytes


@pytest.fixture
def editor(login_as: LoginAs) -> FlaskClient:
    client, _ = login_as("editor")
    return client


def test_usage_shows_space_and_limits(app: Flask, editor: FlaskClient) -> None:
    empty = editor.get(f"{MEDIA}/usage").get_json()["data"]
    assert empty == {
        "used_bytes": 0,
        "quota_bytes": app.config["MEDIA_QUOTA_MB"] * 1024 * 1024,
        "max_upload_bytes": app.config["MAX_CONTENT_LENGTH"],
        "count": 0,
    }
    pdf = uploaded(editor, PDF_BYTES, "a.pdf")
    usage = editor.get(f"{MEDIA}/usage").get_json()["data"]
    assert (usage["used_bytes"], usage["count"]) == (pdf["size_bytes"], 1)


def test_usage_needs_login(api: FlaskClient) -> None:
    assert api.get(f"{MEDIA}/usage").status_code == 401


def test_files_without_folder(editor: FlaskClient) -> None:
    folder = editor.post(FOLDERS, json={"name": "Eventi"}).get_json()["data"]
    loose = uploaded(editor, image_bytes(color=(1, 2, 3)), "sciolta.png")
    uploaded(editor, image_bytes(color=(4, 5, 6)), "in-cartella.png", folder_id=str(folder["id"]))
    ids = [m["id"] for m in editor.get(f"{MEDIA}?folder_id=none").get_json()["data"]]
    assert ids == [loose["id"]]
    assert editor.get(f"{MEDIA}?folder_id=nessuna").status_code == 422


def test_folder_tree_counts_files(editor: FlaskClient) -> None:
    events = editor.post(FOLDERS, json={"name": "Eventi"}).get_json()["data"]
    year = editor.post(FOLDERS, json={"name": "2026", "parent_id": events["id"]}).get_json()["data"]
    uploaded(editor, image_bytes(color=(7, 7, 7)), "a.png", folder_id=str(year["id"]))
    uploaded(editor, image_bytes(color=(8, 8, 8)), "b.png", folder_id=str(year["id"]))
    tree = editor.get(FOLDERS).get_json()["data"]
    assert tree[0]["count"] == 0 and tree[0]["children"][0]["count"] == 2


def test_panel_csp_allows_local_previews_only_for_images(tmp_path: object) -> None:
    from pathlib import Path

    dist = Path(str(tmp_path)) / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<div></div>", encoding="utf-8")
    client = create_app("testing", overrides={"ADMIN_DIST_DIR": dist}).test_client()
    csp = client.get("/admin/").headers["Content-Security-Policy"]
    directives = dict(part.split(" ", 1) for part in csp.split("; "))
    assert (
        directives["img-src"] == "'self' blob:"
    )  # anteprima dei file prima del caricamento (D-118)
    assert [d for d, v in directives.items() if "blob:" in v] == ["img-src"]
