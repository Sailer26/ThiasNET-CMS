"""Media sul sito pubblico (D-75, D-80, D-81): <img> responsive, file, social e distribuzione."""

from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient

from tests.api.test_media_api import MEDIA, uploaded
from tests.conftest import LoginAs
from tests.media_fixtures import PDF_BYTES, image_bytes
from tests.pages_helpers import create_page, doc, publish, put_draft, uid
from tests.render_fixtures import inspect


@pytest.fixture
def admin(login_as: LoginAs) -> FlaskClient:
    client, _ = login_as("admin")
    return client


@pytest.fixture
def visitor(app: Flask) -> FlaskClient:
    return app.test_client()


def _online(client: FlaskClient, blocks: list[dict[str, Any]], **extra: Any) -> None:
    page = create_page(client, "Galleria")
    put_draft(
        client, page["id"], doc(title="Galleria", zones={"main": blocks, "sidebar": []}, **extra)
    )
    assert publish(client, page["id"]).status_code == 200


def test_images_are_responsive_with_alt_and_focal_classes(
    admin: FlaskClient, visitor: FlaskClient
) -> None:
    media = uploaded(admin, image_bytes(size=(1600, 1200)), alt='Lago "blu" <sera>')
    admin.patch(f"{MEDIA}/{media['id']}", json={"version": 1, "focal_x": 20})
    _online(admin, [{"uid": uid(1), "type": "image", "data": {"media_id": media["id"]}}])
    html = visitor.get("/galleria").get_data(as_text=True)
    [img] = inspect(html).find("img")
    assert img["alt"] == 'Lago "blu" <sera>'  # escapato nell'HTML, intatto per chi legge
    assert img["loading"] == "lazy" and img["width"] and img["height"]
    assert img["srcset"] and "1024w" in img["srcset"]
    assert "cms-fx-2" in (img["class"] or "")
    assert "style=" not in html
    assert any(a.get("href") == "/static/cms/media.css" for a in inspect(html).find("link"))


def test_social_tags_use_the_site_address(admin: FlaskClient, visitor: FlaskClient) -> None:
    media = uploaded(admin, image_bytes(size=(1600, 1000)), alt="Piazza")
    _online(admin, [{"uid": uid(1), "type": "image", "data": {"media_id": media["id"]}}])
    metas = inspect(visitor.get("/galleria").get_data(as_text=True)).find("meta")
    og = {m.get("property"): m.get("content") for m in metas if m.get("property")}
    assert str(og["og:image"]).startswith("https://www.example.ch/media/")
    assert (og["og:image:width"], og["og:image:height"]) == ("1200", "630")
    assert og["og:url"] == "https://www.example.ch/galleria"


def test_files_show_name_format_and_size(admin: FlaskClient, visitor: FlaskClient) -> None:
    pdf = uploaded(admin, PDF_BYTES, "Regolamento comunale.pdf")
    _online(admin, [{"uid": uid(1), "type": "files", "data": {"items": [{"media_id": pdf["id"]}]}}])
    html = visitor.get("/galleria").get_data(as_text=True)
    assert f'href="{pdf["url"]}"' in html
    assert "Regolamento comunale.pdf" in html and "(PDF, 1 kB)" in html


def test_alt_change_reaches_the_cached_page(admin: FlaskClient, visitor: FlaskClient) -> None:
    media = uploaded(admin, alt="Prima")
    _online(admin, [{"uid": uid(1), "type": "image", "data": {"media_id": media["id"]}}])
    assert 'alt="Prima"' in visitor.get("/galleria").get_data(as_text=True)
    admin.patch(f"{MEDIA}/{media['id']}", json={"version": 1, "alt": "Dopo"})
    assert 'alt="Dopo"' in visitor.get("/galleria").get_data(as_text=True)


# --- Distribuzione /media (D-75) ------------------------------------------------------------


def test_images_are_served_immutable_and_sandboxed(
    admin: FlaskClient, visitor: FlaskClient
) -> None:
    media = uploaded(admin)
    response = visitor.get(media["url"])
    assert response.status_code == 200
    assert response.mimetype in {"image/png", "image/jpeg", "image/webp"}
    assert "immutable" in response.headers["Cache-Control"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Content-Security-Policy"] == "default-src 'none'; sandbox"
    assert visitor.get(media["thumbnail_url"]).status_code == 200


def test_pdfs_are_always_downloads_with_their_name(
    admin: FlaskClient, visitor: FlaskClient
) -> None:
    pdf = uploaded(admin, PDF_BYTES, "Orari estate.pdf")
    response = visitor.get(pdf["url"])
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.headers["Content-Disposition"].startswith("attachment")
    assert "Orari" in response.headers["Content-Disposition"]
    assert "max-age=300" in response.headers["Cache-Control"]
    assert (
        visitor.get(pdf["url"], headers={"If-None-Match": response.headers["ETag"]}).status_code
        == 304
    )


def test_only_current_files_of_known_media_are_served(
    admin: FlaskClient, visitor: FlaskClient
) -> None:
    media = uploaded(admin)
    old_url = media["url"]
    admin.patch(f"{MEDIA}/{media['id']}", json={"version": 1, "focal_x": 0})  # nuova revisione
    assert visitor.get(old_url).status_code == 404
    key = media["key"]
    for path in (
        f"/media/{key}/r9-master.png",
        f"/media/{key}/../../theme.json",
        f"/media/{'0' * 32}/r1-master.png",
        "/media/non-una-chiave/r1-master.png",
        f"/media/{key}/file.pdf",  # un'immagine non ha un PDF
    ):
        assert visitor.get(path).status_code == 404, path


def test_missing_media_disappears_on_the_site(
    admin: FlaskClient, visitor: FlaskClient, app: Flask
) -> None:
    media = uploaded(admin, alt="Foto")
    _online(admin, [{"uid": uid(1), "type": "image", "data": {"media_id": media["id"]}}])
    from app.extensions import db
    from app.models.media import Media

    with app.app_context():  # simulazione: il media sparisce senza passare dalla libreria
        db.session.delete(db.session.get(Media, media["id"]))
        db.session.commit()
        from app.services import page_cache

        page_cache.mark_changed()
        db.session.commit()
    response = visitor.get("/galleria")
    assert response.status_code == 200
    assert inspect(response.get_data(as_text=True)).find("img") == []


# --- Regressioni dalla review ECC della Fase 4 -------------------------------------------


def test_media_responses_never_carry_the_session_cookie(admin: FlaskClient) -> None:
    media = uploaded(admin)
    response = admin.get(media["url"])  # chi è loggato nel pannello
    assert response.status_code == 200
    assert "Set-Cookie" not in response.headers
    assert "Cookie" not in response.headers.get("Vary", "")
