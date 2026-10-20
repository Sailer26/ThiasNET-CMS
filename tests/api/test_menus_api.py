"""Menu del sito (Fase 6b, D-140, D-141, D-145): albero intero salvato con versione."""

from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient

from tests.conftest import LoginAs
from tests.helpers import API, error_code
from tests.pages_helpers import actions, create_page, publish, trash, uid

MENUS = f"{API}/menus"


@pytest.fixture
def admin(login_as: LoginAs) -> FlaskClient:
    client, _ = login_as("admin")
    return client


def online(client: FlaskClient, title: str, **extra: Any) -> dict[str, Any]:
    page = create_page(client, title, **extra)
    assert publish(client, page["id"]).status_code == 200
    return page


def menus(client: FlaskClient) -> dict[str, dict[str, Any]]:
    response = client.get(MENUS)
    assert response.status_code == 200, response.get_json()
    return {menu["location"]: menu for menu in response.get_json()["data"]}


def item(n: int, **extra: Any) -> dict[str, Any]:
    return {"uid": uid(n), "children": [], **extra}


def put(
    client: FlaskClient, location: str, items: list[dict[str, Any]], version: int | None = None
) -> Any:
    known = menus(client)[location]["version"] if version is None else version
    return client.put(f"{MENUS}/{location}", json={"version": known, "items": items})


def details(response: Any) -> set[tuple[str, str]]:
    found = (response.get_json() or {}).get("error", {}).get("details") or []
    return {(d["path"], d["code"]) for d in found}


def test_only_who_can_publish(login_as: LoginAs) -> None:
    editor, _ = login_as("editor")  # senza "può pubblicare"
    assert editor.get(MENUS).status_code == 403
    assert editor.put(f"{MENUS}/main", json={"version": 0, "items": []}).status_code == 403


def test_main_is_automatic_until_the_first_save(admin: FlaskClient) -> None:
    home = online(admin, "Home")
    about = online(admin, "Chi siamo")
    found = menus(admin)
    main, footer = found["main"], found["footer"]
    assert (main["manual"], main["version"], main["max_depth"], main["label"]) == (
        False,
        0,
        2,
        "Menu principale",
    )
    assert [i["page_id"] for i in main["items"]] == [home["id"], about["id"]]
    assert footer["manual"] is False and footer["items"] == []
    assert admin.get(f"{MENUS}/nessuno").status_code == 404


def test_saved_tree_reaches_the_site(app: Flask, admin: FlaskClient) -> None:
    home = online(admin, "Home")
    services = online(admin, "Servizi")
    items = [
        item(1, page_id=home["id"]),
        item(
            2,
            page_id=services["id"],
            label="I nostri servizi",
            children=[item(3, url="https://www.esterno.ch/orari", label="Orari esterni")],
        ),
    ]
    response = put(admin, "main", items)
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert (data["manual"], data["version"]) == (True, 1)
    assert "menu.updated" in actions(app)
    html = admin.get("/").get_data(as_text=True)
    assert ">I nostri servizi</a>" in html
    assert 'href="https://www.esterno.ch/orari"' in html and "Orari esterni" in html
    assert "site-nav__sub" in html


def test_page_title_follows_the_page_and_offline_pages_are_hidden(admin: FlaskClient) -> None:
    home = online(admin, "Home")
    news = online(admin, "Notizie")
    gone = online(admin, "Vecchia")
    items = [
        item(1, page_id=home["id"]),
        item(2, page_id=news["id"]),
        item(
            3, page_id=gone["id"], children=[item(4, url="/notizie", label="Figlia della vecchia")]
        ),
    ]
    assert put(admin, "main", items).status_code == 200
    assert trash(admin, gone["id"]).status_code == 200
    html = admin.get("/").get_data(as_text=True)
    assert ">Notizie</a>" in html
    assert "Vecchia" not in html and "Figlia della vecchia" not in html  # sparisce con le sottovoci


@pytest.mark.parametrize(
    ("location", "items", "problem"),
    [
        (
            "footer",
            [item(1, url="/a", label="A", children=[item(2, url="/b", label="B")])],
            ("items/0/children", "too_deep"),
        ),
        ("main", [item(1, url="/a")], ("items/0/label", "label_required")),
        ("main", [item(1, url="javascript:alert(1)", label="X")], ("items/0/url", "invalid_url")),
        ("main", [item(1, page_id=999999)], ("items/0/page_id", "page_missing")),
        ("main", [item(1, page_id=1, url="/a", label="X")], ("items/0", "invalid_target")),
        ("main", [item(1)], ("items/0", "invalid_target")),
        ("main", [item(1, url="/a", label="x" * 81)], ("items/0/label", "max_length")),
        (
            "main",
            [item(1, url="/a", label="A"), item(1, url="/b", label="B")],
            ("items/1/uid", "duplicate_uid"),
        ),
        ("main", [item(n, url=f"/p{n}", label="P") for n in range(61)], ("items", "too_many")),
    ],
)
def test_validation(
    admin: FlaskClient, location: str, items: list[dict[str, Any]], problem: tuple[str, str]
) -> None:
    response = put(admin, location, items)
    assert response.status_code == 422, response.get_json()
    assert problem in details(response)


def test_shape_is_checked(admin: FlaskClient) -> None:
    bad = admin.put(f"{MENUS}/main", json={"version": 0, "items": [{"uid": "x", "evil": 1}]})
    assert bad.status_code == 422


def test_version_conflict(admin: FlaskClient) -> None:
    home = online(admin, "Home")
    assert put(admin, "main", [item(1, page_id=home["id"])]).status_code == 200
    response = put(admin, "main", [], version=0)
    assert (response.status_code, error_code(response)) == (409, "version_conflict")


def test_back_to_automatic(app: Flask, admin: FlaskClient) -> None:
    home = online(admin, "Home")
    online(admin, "Chi siamo")
    assert put(admin, "main", [item(1, page_id=home["id"], label="Inizio")]).status_code == 200
    assert ">Inizio</a>" in admin.get("/").get_data(as_text=True)
    version = menus(admin)["main"]["version"]
    response = admin.delete(f"{MENUS}/main", json={"version": version})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["data"]["manual"] is False
    assert "menu.reset" in actions(app)
    html = admin.get("/").get_data(as_text=True)
    assert ">Chi siamo</a>" in html and ">Inizio</a>" not in html


def test_footer_menu_is_rendered(admin: FlaskClient) -> None:
    online(admin, "Home")
    assert put(admin, "footer", [item(1, url="/privacy", label="Privacy")]).status_code == 200
    html = admin.get("/").get_data(as_text=True)
    assert 'class="footer-nav"' in html and ">Privacy</a>" in html


def test_absurdly_nested_tree_is_422_not_500(admin: FlaskClient) -> None:
    tree: dict[str, Any] = {"uid": uid(1), "url": "/a", "label": "A", "children": []}
    for n in range(2, 700):
        tree = {"uid": uid(n), "url": "/a", "label": "A", "children": [tree]}
    response = put(admin, "main", [tree])
    assert response.status_code == 422


def test_child_page_is_marked_current(admin: FlaskClient) -> None:
    services = online(admin, "Servizi")
    hours = online(admin, "Orari", parent_id=services["id"])
    items = [item(1, page_id=services["id"], children=[item(2, page_id=hours["id"])])]
    assert put(admin, "main", items).status_code == 200
    html = admin.get("/servizi/orari").get_data(as_text=True)
    assert '<a href="/servizi/orari" aria-current="page">Orari</a>' in html


def test_menu_follows_a_new_address(admin: FlaskClient) -> None:
    from tests.pages_helpers import PAGES, page_version

    page = online(admin, "Chi siamo")
    assert put(admin, "main", [item(1, page_id=page["id"])]).status_code == 200
    moved = admin.patch(
        f"{PAGES}/{page['id']}", json={"version": page_version(admin, page["id"]), "slug": "noi"}
    )
    assert moved.status_code == 200, moved.get_json()
    assert 'href="/noi"' in admin.get("/noi").get_data(as_text=True)


def test_levels_beyond_the_theme_are_cut_when_shown(app: Flask, admin: FlaskClient) -> None:
    """Un tema che riduce i livelli: le sottovoci salvate prima non si vedono (D-53)."""
    from app.extensions import db
    from app.models.menu import MenuRow

    online(admin, "Home")
    deep = [item(1, url="/a", label="Sopra", children=[item(2, url="/b", label="Sotto")])]
    with app.app_context():
        db.session.add(MenuRow(location="footer", locale="it", items_json=deep, version=1))
        db.session.commit()
    html = admin.get("/").get_data(as_text=True)
    assert ">Sopra</a>" in html and "Sotto" not in html


def test_reset_with_old_version_is_409_and_without_menu_is_harmless(admin: FlaskClient) -> None:
    assert admin.delete(f"{MENUS}/footer", json={"version": 0}).status_code == 200
    assert put(admin, "footer", [item(1, url="/a", label="A")]).status_code == 200
    stale = admin.delete(f"{MENUS}/footer", json={"version": 0})
    assert (stale.status_code, error_code(stale)) == (409, "version_conflict")


def test_automatic_menu_has_stable_uids(admin: FlaskClient) -> None:
    online(admin, "Home")
    first = [i["uid"] for i in menus(admin)["main"]["items"]]
    assert first == [i["uid"] for i in menus(admin)["main"]["items"]]
