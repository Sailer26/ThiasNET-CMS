"""Widget per area (Fase 6c, D-140, D-142, D-146): lista intera per area, salvata con versione."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient

from tests.conftest import LoginAs
from tests.helpers import API, error_code
from tests.pages_helpers import actions, create_page, publish, uid

WIDGETS = f"{API}/widgets"


@pytest.fixture
def admin(login_as: LoginAs) -> FlaskClient:
    client, _ = login_as("admin")
    return client


def online(client: FlaskClient, title: str) -> dict[str, Any]:
    page = create_page(client, title)
    assert publish(client, page["id"]).status_code == 200
    return page


def areas(client: FlaskClient) -> dict[str, dict[str, Any]]:
    response = client.get(WIDGETS)
    assert response.status_code == 200, response.get_json()
    return {area["area"]: area for area in response.get_json()["data"]}


def widget(n: int, kind: str, data: dict[str, Any] | None, **extra: Any) -> dict[str, Any]:
    return {"uid": uid(n), "type": kind, "data": data, **extra}


def put(
    client: FlaskClient, area: str, items: list[dict[str, Any]], version: int | None = None
) -> Any:
    known = areas(client)[area]["version"] if version is None else version
    return client.put(f"{WIDGETS}/{area}", json={"version": known, "items": items})


def details(response: Any) -> set[tuple[str, str]]:
    found = (response.get_json() or {}).get("error", {}).get("details") or []
    return {(d["path"], d["code"]) for d in found}


def test_only_who_can_publish(login_as: LoginAs) -> None:
    editor, _ = login_as("editor")
    assert editor.get(WIDGETS).status_code == 403
    assert editor.get(f"{WIDGETS}/footer").status_code == 403
    assert editor.put(f"{WIDGETS}/footer", json={"version": 0, "items": []}).status_code == 403


def test_areas_list_the_widgets_the_theme_allows(admin: FlaskClient) -> None:
    found = areas(admin)
    assert set(found) == {"header_top", "footer", "sidebar"}
    footer = found["footer"]
    assert footer["label"] == "Piè di pagina" and footer["version"] == 0 and footer["items"] == []
    assert footer["locale"] == "it"  # le pagine della visibilità sono di questa lingua
    types = [t["type"] for t in footer["types"]]
    assert types == [
        "hours",
        "contacts",
        "social",
        "text",
    ]  # "ultime notizie" con la Fase 7 (D-142)
    hours = next(t for t in footer["types"] if t["type"] == "hours")
    assert hours["label"] == "Orari" and hours["schema"]["properties"]["rows"]["type"] == "array"
    assert admin.get(f"{WIDGETS}/nessuna").status_code == 404


def test_saved_widgets_reach_the_site_cleaned(app: Flask, admin: FlaskClient) -> None:
    page = online(admin, "Home")
    items = [
        widget(
            1,
            "hours",
            {"title": "Orari", "rows": [{"days": "Lunedì - Venerdì", "hours": "8:00 - 12:00"}]},
        ),
        widget(
            2,
            "text",
            {"title": "Chi siamo", "body": "<p>Ciao <script>x</script><strong>tutti</strong></p>"},
        ),
    ]
    response = put(admin, "footer", items)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["data"]["version"] == 1
    assert "widget.area_updated" in actions(app)
    html = admin.get(page["path"]).get_data(as_text=True)
    assert "Lunedì - Venerdì" in html and "8:00 - 12:00" in html
    assert "<strong>tutti</strong>" in html and "<script>x</script>" not in html
    assert f'data-widget-id="{uid(1)}"' in html


def test_visibility_per_page(admin: FlaskClient) -> None:
    home = online(admin, "Home")
    about = online(admin, "Chi siamo")
    cta = {"button_label": "Vai", "url": "/contatti"}
    only = widget(
        1, "cta", {"title": "Solo qui", **cta}, visibility={"mode": "only", "pages": [about["id"]]}
    )
    skip = widget(
        2,
        "cta",
        {"title": "Tranne qui", **cta},
        visibility={"mode": "except", "pages": [about["id"]]},
    )
    assert put(admin, "sidebar", [only, skip]).status_code == 200
    about_html = admin.get(about["path"]).get_data(as_text=True)
    other_html = admin.get(home["path"]).get_data(as_text=True)
    assert "Solo qui" in about_html and "Tranne qui" not in about_html
    assert "Solo qui" not in other_html and "Tranne qui" in other_html


def test_expired_notice_disappears_and_refreshes_the_cache(
    app: Flask, admin: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import page_cache, widgets

    page = online(admin, "Home")
    until = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    notice = widget(1, "notice", {"text": "Uffici chiusi oggi", "level": "warning"}, until=until)
    assert put(admin, "header_top", [notice]).status_code == 200
    assert "Uffici chiusi oggi" in admin.get(page["path"]).get_data(as_text=True)
    later = datetime.now(UTC) + timedelta(hours=2)
    monkeypatch.setattr(widgets, "_now", lambda: later)
    with app.app_context():
        before = page_cache.current_generation()
    assert "Uffici chiusi oggi" not in admin.get(page["path"]).get_data(as_text=True)
    with app.app_context():
        assert page_cache.current_generation() > before  # la cache non tiene il banner scaduto


def test_contacts_and_social_use_the_site_data(admin: FlaskClient) -> None:
    page = online(admin, "Home")
    site = admin.get(f"{API}/settings").get_json()["data"]["site"]
    values = {
        "name": "Comune",
        "email": "info@prova.ch",
        "facebook": "https://www.facebook.com/prova",
    }
    stored = admin.put(f"{API}/settings/site", json={"version": site["version"], "values": values})
    assert stored.status_code == 200
    items = [widget(1, "contacts", {"title": "Contatti"}), widget(2, "social", {})]
    assert put(admin, "footer", items).status_code == 200
    html = admin.get(page["path"]).get_data(as_text=True)
    assert 'href="mailto:info@prova.ch"' in html
    assert 'href="https://www.facebook.com/prova"' in html


@pytest.mark.parametrize(
    ("area", "items", "problem"),
    [
        ("header_top", [widget(1, "text", {"body": "<p>x</p>"})], ("items/0/type", "not_allowed")),
        ("footer", [widget(1, "latest_entries", {})], ("items/0/type", "not_allowed")),
        ("header_top", [widget(1, "notice", {})], ("items/0/data/text", "required")),
        (
            "footer",
            [widget(n, "text", {"body": "<p>x</p>"}) for n in range(21)],
            ("items", "too_many"),
        ),
        (
            "footer",
            [widget(1, "text", {"body": "<p>x</p>"}), widget(1, "text", {"body": "<p>y</p>"})],
            ("items/1/uid", "duplicate_uid"),
        ),
        (
            "footer",
            [widget(1, "text", {"body": "<p>x</p>"}, visibility={"mode": "forse", "pages": []})],
            ("items/0/visibility", "invalid_visibility"),
        ),
        (
            "footer",
            [
                widget(
                    1, "text", {"body": "<p>x</p>"}, visibility={"mode": "only", "pages": [999999]}
                )
            ],
            ("items/0/visibility/pages", "page_missing"),
        ),
        (
            "header_top",
            [widget(1, "notice", {"text": "x"}, until="2026-12-01T10:00:00")],
            ("items/0/until", "invalid_until"),
        ),
        (
            "header_top",
            [widget(1, "notice", {"text": "x"}, until="0001-01-01T00:00:00+05:00")],
            ("items/0/until", "invalid_until"),
        ),
        (
            "header_top",
            [widget(1, "notice", {"text": "x"}, until="9999-12-31T23:59:59-05:00")],
            ("items/0/until", "invalid_until"),
        ),
        (
            "footer",
            [widget(1, "text", {"body": "<p>x</p>"}, until="2099-01-01T10:00:00+01:00")],
            ("items/0/until", "until_not_allowed"),
        ),
        ("footer", [widget(1, "text", None)], ("items/0/data", "invalid_shape")),
        (
            "footer",
            [{"uid": uid(1), "type": "text", "data": {"body": "x"}, "evil": 1}],
            ("items/0", "invalid_shape"),
        ),
    ],
)
def test_validation(
    admin: FlaskClient, area: str, items: list[dict[str, Any]], problem: tuple[str, str]
) -> None:
    response = put(admin, area, items)
    assert response.status_code == 422, response.get_json()
    assert problem in details(response)


def test_version_conflict(admin: FlaskClient) -> None:
    assert put(admin, "footer", [widget(1, "text", {"body": "<p>x</p>"})]).status_code == 200
    response = put(admin, "footer", [], version=0)
    assert (response.status_code, error_code(response)) == (409, "version_conflict")
