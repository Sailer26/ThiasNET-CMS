"""Prima di pubblicare: media esistenti, del tipo giusto e con testo alternativo (D-77, D-78)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from flask.testing import FlaskClient

from tests.api.test_media_api import uploaded
from tests.conftest import LoginAs
from tests.helpers import error_code
from tests.media_fixtures import PDF_BYTES
from tests.pages_helpers import PAGES, create_page, details, doc, publish, put_draft, uid


@pytest.fixture
def admin(login_as: LoginAs) -> FlaskClient:
    client, _ = login_as("admin")
    return client


def _page_with(client: FlaskClient, block: dict[str, Any], **extra: Any) -> dict[str, Any]:
    page = create_page(client, "Pagina")
    response = put_draft(client, page["id"], doc(zones={"main": [block], "sidebar": []}, **extra))
    assert response.status_code == 200  # la bozza non controlla mai i media (D-46)
    return page


def _image(media_id: int) -> dict[str, Any]:
    return {"uid": uid(1), "type": "image", "data": {"media_id": media_id}}


@pytest.mark.parametrize(
    ("make", "code"),
    [
        (lambda c: 9999, "media_missing"),
        (lambda c: uploaded(c, PDF_BYTES, "x.pdf")["id"], "media_not_image"),
        (lambda c: uploaded(c)["id"], "alt_missing"),
    ],
)
def test_publishing_checks_the_media(admin: FlaskClient, make: Any, code: str) -> None:
    page = _page_with(admin, _image(make(admin)))
    response = publish(admin, page["id"])
    assert (response.status_code, error_code(response)) == (422, "invalid_content")
    assert ("zones/main/0/data/media_id", code) in details(response)


def test_image_with_alt_can_be_published(admin: FlaskClient) -> None:
    media = uploaded(admin, alt="Municipio")
    assert publish(admin, _page_with(admin, _image(media["id"]))["id"]).status_code == 200


def test_files_block_accepts_documents(admin: FlaskClient) -> None:
    pdf = uploaded(admin, PDF_BYTES, "orari.pdf")
    files = {"uid": uid(1), "type": "files", "data": {"items": [{"media_id": pdf["id"]}]}}
    assert publish(admin, _page_with(admin, files)["id"]).status_code == 200


def test_social_image_is_checked_too(admin: FlaskClient) -> None:
    media = uploaded(admin)
    text = {"uid": uid(1), "type": "text", "data": {"body": "<p>x</p>"}}
    page = _page_with(admin, text, seo={"og_image_media_id": media["id"]})
    assert ("seo/og_image_media_id", "alt_missing") in details(publish(admin, page["id"]))


def test_scheduling_checks_the_media_too(admin: FlaskClient) -> None:
    page = _page_with(admin, _image(9999))
    when = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    response = admin.post(
        f"{PAGES}/{page['id']}/schedule", json={"draft_version": 2, "publish_at": when}
    )
    assert ("zones/main/0/data/media_id", "media_missing") in details(response)
