"""Controllo prima di pubblicare (5d-1, D-135): bloccanti come `publish`, avvisi che non bloccano."""

from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient

from tests.api.test_media_api import uploaded
from tests.conftest import LoginAs
from tests.pages_helpers import PAGES, create_page, details, doc, publish, put_draft, trash, uid

SEO = {"description": "Una pagina di prova."}


@pytest.fixture
def admin(login_as: LoginAs) -> FlaskClient:
    client, _ = login_as("admin")
    return client


def checks(client: FlaskClient, page_id: int) -> dict[str, Any]:
    response = client.get(f"{PAGES}/{page_id}/checks")
    assert response.status_code == 200, response.get_json()
    data: dict[str, Any] = response.get_json()["data"]
    return data


def codes(items: list[dict[str, str]]) -> set[tuple[str, str]]:
    return {(item["path"], item["code"]) for item in items}


def text(n: int, body: str) -> dict[str, Any]:
    return {"uid": uid(n), "type": "text", "data": {"body": body}}


def cta(n: int, url: str) -> dict[str, Any]:
    data = {"title": "Vieni", "button_label": "Vai", "url": url}
    return {"uid": uid(n), "type": "cta", "data": data}


def page_with(
    client: FlaskClient,
    *blocks: dict[str, Any],
    seo: dict[str, Any] | None = None,
    title: str = "Prova",
) -> dict[str, Any]:
    page = create_page(client, title or "Senza titolo")
    zones = {"main": list(blocks), "sidebar": []}
    body = doc(title=title, zones=zones, seo=SEO if seo is None else seo)
    assert put_draft(client, page["id"], body).status_code == 200
    return page


def online(client: FlaskClient, title: str) -> dict[str, Any]:
    page = page_with(client, text(1, "<p>Ciao</p>"), title=title)
    assert publish(client, page["id"]).status_code == 200
    return page


def test_permissions_and_missing_page(login_as: LoginAs) -> None:
    admin, _ = login_as("admin")
    page = create_page(admin)
    editor, _ = login_as("editor")  # senza "può pubblicare"
    assert editor.get(f"{PAGES}/{page['id']}/checks").status_code == 403
    assert admin.get(f"{PAGES}/999999/checks").status_code == 404


def test_a_good_page_has_nothing_to_report(admin: FlaskClient) -> None:
    page = page_with(admin, text(1, "<p>Benvenuti</p>"))
    assert checks(admin, page["id"]) == {"blocking": [], "warnings": []}


def test_empty_page_and_missing_seo_are_warnings_only(admin: FlaskClient) -> None:
    page = page_with(admin, seo={})
    result = checks(admin, page["id"])
    assert result["blocking"] == []
    assert codes(result["warnings"]) == {("zones", "page_empty"), ("seo/description", "seo_empty")}
    assert all(item["message"] for item in result["warnings"])
    assert publish(admin, page["id"]).status_code == 200  # avvisano, non bloccano


def test_blocking_problems_are_the_same_as_publish(admin: FlaskClient) -> None:
    image = {"uid": uid(1), "type": "image", "data": {"media_id": uploaded(admin)["id"]}}
    page = page_with(admin, image, title="")
    result = checks(admin, page["id"])
    response = publish(admin, page["id"])
    assert response.status_code == 422
    assert codes(result["blocking"]) == details(response)
    assert ("zones/main/0/data/media_id", "alt_missing") in codes(result["blocking"])
    assert ("title", "required") in codes(result["blocking"])


def test_internal_links(app: Flask, admin: FlaskClient) -> None:
    online(admin, "Chi siamo")
    draft_only = page_with(admin, text(1, "<p>x</p>"), title="Solo bozza")
    gone = online(admin, "Vecchia")
    assert trash(admin, gone["id"]).status_code == 200
    media = uploaded(admin, alt="Lago")
    good = [
        "/chi-siamo",
        "/chi-siamo?x=1#sopra",
        "#sopra",
        "https://www.esterno.ch/pagina",
        "mailto:info@example.ch",
        f"{app.config['SITE_URL']}/chi-siamo",
        media["url"],
    ]
    good += ["/chi-siamo/", "/it/chi-siamo"]  # forme che il sito corregge con un redirect
    bad = ["/non-esiste", draft_only["path"], "/vecchia", "/media/" + "0" * 32 + "/x.webp"]
    body = "".join(f'<p><a href="{href}">link</a></p>' for href in good)
    blocks = [text(1, body), *(cta(n + 2, href) for n, href in enumerate(bad))]
    blocks.append(text(9, '<p><a href="/non-esiste-nemmeno">rotto</a></p>'))
    page = page_with(admin, *blocks)

    assert codes(checks(admin, page["id"])["warnings"]) == {
        ("zones/main/1/data/url", "link_broken"),
        ("zones/main/2/data/url", "link_broken"),
        ("zones/main/3/data/url", "link_broken"),
        ("zones/main/4/data/url", "link_broken"),
        ("zones/main/5/data/body", "link_broken"),
    }


def test_redirect_forms_of_missing_pages_are_broken(admin: FlaskClient) -> None:
    page = page_with(admin, cta(1, "/non-esiste/"), cta(2, "/it/non-esiste"))
    assert codes(checks(admin, page["id"])["warnings"]) == {
        ("zones/main/0/data/url", "link_broken"),
        ("zones/main/1/data/url", "link_broken"),
    }


def test_plain_text_that_starts_with_a_slash_is_not_a_link(admin: FlaskClient) -> None:
    heading = {"uid": uid(1), "type": "heading", "data": {"text": "/ aperti 24 ore"}}
    page = page_with(admin, heading)
    assert checks(admin, page["id"])["warnings"] == []


def test_published_page_without_draft_checks_what_is_online(admin: FlaskClient) -> None:
    page = page_with(admin, text(1, "<p>Ciao</p>"), seo={})
    assert publish(admin, page["id"]).status_code == 200
    result = checks(admin, page["id"])
    assert result["blocking"] == []
    assert codes(result["warnings"]) == {("seo/description", "seo_empty")}
