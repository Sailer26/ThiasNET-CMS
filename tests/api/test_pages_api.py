"""Pagine: creazione, albero, slug e percorsi, spostamenti, riordino, cestino (D-43, D-45)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import select

from app.extensions import db
from app.models.page import PageRedirect
from tests.conftest import LoginAs
from tests.helpers import error_code
from tests.pages_helpers import (
    PAGES,
    actions,
    create_page,
    page_version,
    publish,
    restore,
    trash,
)


def _patch(client: FlaskClient, page_id: int, **changes: Any) -> Any:
    return client.patch(
        f"{PAGES}/{page_id}", json={"version": page_version(client, page_id), **changes}
    )


def _redirects(app: Flask) -> set[tuple[str, str, int]]:
    with app.app_context():
        rows = db.session.execute(select(PageRedirect)).scalars()
        return {(r.locale, r.from_path, r.page_id) for r in rows}


def _chain(client: FlaskClient, depth: int) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for level in range(depth):
        parent = {"parent_id": pages[-1]["id"]} if pages else {}
        pages.append(create_page(client, f"Livello {level + 1}", **parent))
    return pages


# --- Accesso -----------------------------------------------------------------


def test_pages_require_login(api: Any) -> None:
    assert api.get(PAGES).status_code == 401
    assert api.post(PAGES, json={"title": "x", "layout": "page"}).status_code == 401


# --- Creazione ---------------------------------------------------------------


def test_editor_creates_page_with_slug_from_title(app: Flask, login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    page = create_page(client, "Über uns")
    assert (page["slug"], page["path"], page["locale"]) == ("ueber-uns", "/ueber-uns", "it")
    assert (page["status"], page["version"], page["has_draft"]) == ("draft", 1, True)
    assert page["is_home"] is False
    assert len(page["translation_group"]) == 36
    assert "page.created" in actions(app)


def test_new_page_starts_with_empty_draft(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    page = create_page(client)
    draft = client.get(f"{PAGES}/{page['id']}/draft").get_json()["data"]
    assert draft["version"] == 1
    assert draft["data"] == {
        "title": "Chi siamo",
        "layout": "page",
        "seo": {},
        "zones": {"main": [], "sidebar": []},
    }


def test_auto_slug_collision_gets_a_suffix(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    create_page(client)
    assert create_page(client)["slug"] == "chi-siamo-2"
    assert create_page(client)["slug"] == "chi-siamo-3"


def test_explicit_slug_taken_is_409(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    create_page(client, slug="contatti")
    response = client.post(PAGES, json={"title": "Altro", "layout": "page", "slug": "contatti"})
    assert response.status_code == 409
    assert error_code(response) == "slug_taken"


def test_title_without_letters_gets_a_fallback_slug(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    assert create_page(client, "日本")["slug"] == "pagina"


def test_reserved_slugs_only_at_first_level(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    response = client.post(PAGES, json={"title": "Api", "layout": "page", "slug": "api"})
    assert (response.status_code, error_code(response)) == (422, "reserved_slug")
    assert create_page(client, "Admin")["slug"] == "admin-2"  # automatico: si evita da solo
    parent = create_page(client, "Servizi")
    assert create_page(client, "De", parent_id=parent["id"])["path"] == "/servizi/de"


def test_invalid_input_is_422(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    cases = [
        ({"title": "x", "layout": "landing"}, "unknown_layout"),
        ({"title": "x", "layout": "page", "locale": "fr"}, "unknown_locale"),
        ({"title": "x", "layout": "page", "slug": "Non Valido"}, "invalid_slug"),
        ({"title": "   ", "layout": "page"}, "invalid_title"),
        ({"title": "x", "layout": "page", "extra": 1}, "invalid_body"),
    ]
    for body, code in cases:
        response = client.post(PAGES, json=body)
        assert (response.status_code, error_code(response)) == (422, code), body


def test_parent_must_exist_and_share_the_locale(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    assert (
        client.post(PAGES, json={"title": "x", "layout": "page", "parent_id": 999}).status_code
        == 404
    )
    german = create_page(client, "Dienste", locale="de")
    response = client.post(PAGES, json={"title": "x", "layout": "page", "parent_id": german["id"]})
    assert (response.status_code, error_code(response)) == (422, "parent_locale_mismatch")


def test_homepage_one_per_locale_without_children(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    home = create_page(client, "Home", layout="home", slug="")
    assert (home["path"], home["is_home"]) == ("/", True)
    again = client.post(PAGES, json={"title": "Home 2", "layout": "home", "slug": ""})
    assert (again.status_code, error_code(again)) == (409, "home_exists")
    assert create_page(client, "Start", layout="home", slug="", locale="de")["path"] == "/"
    child = client.post(PAGES, json={"title": "Figlia", "layout": "page", "parent_id": home["id"]})
    assert (child.status_code, error_code(child)) == (422, "home_has_no_children")


def test_maximum_depth_is_four_levels(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    chain = _chain(client, 4)
    assert chain[-1]["path"] == "/livello-1/livello-2/livello-3/livello-4"
    response = client.post(
        PAGES, json={"title": "5", "layout": "page", "parent_id": chain[-1]["id"]}
    )
    assert (response.status_code, error_code(response)) == (422, "too_deep")


# --- Lettura -----------------------------------------------------------------


def test_get_list_filters_and_paginates(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    parent = create_page(client, "Servizi")
    create_page(client, "Scuola", parent_id=parent["id"])
    create_page(client, "Rifiuti", parent_id=parent["id"])
    create_page(client, "Dienste", locale="de")
    assert client.get(f"{PAGES}/{parent['id']}").get_json()["data"]["title"] == "Servizi"

    body = client.get(f"{PAGES}?locale=it&limit=2").get_json()
    assert body["meta"] == {"page": 1, "limit": 2, "total": 3}
    children = client.get(f"{PAGES}?parent_id={parent['id']}").get_json()["data"]
    assert {p["title"] for p in children} == {"Scuola", "Rifiuti"}
    assert [p["title"] for p in client.get(f"{PAGES}?q=scu").get_json()["data"]] == ["Scuola"]
    assert client.get(f"{PAGES}?status=published").get_json()["data"] == []
    assert client.get(f"{PAGES}?status=online").status_code == 422


def test_tree_is_nested_with_home_first(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    servizi = create_page(client, "Servizi")
    create_page(client, "Scuola", parent_id=servizi["id"])
    create_page(client, "Home", layout="home", slug="")
    tree = client.get(f"{PAGES}/tree?locale=it").get_json()["data"]
    assert [node["title"] for node in tree] == ["Home", "Servizi"]
    assert [node["title"] for node in tree[1]["children"]] == ["Scuola"]


def test_missing_page_is_404(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    assert client.get(f"{PAGES}/999").status_code == 404


# --- Slug e spostamenti -----------------------------------------------------------


def test_changing_slug_updates_descendant_paths(app: Flask, login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    parent = create_page(client, "Servizi")
    child = create_page(client, "Scuola", parent_id=parent["id"])
    response = _patch(client, parent["id"], slug="uffici")
    assert response.status_code == 200
    assert response.get_json()["data"]["version"] == parent["version"] + 1
    assert client.get(f"{PAGES}/{child['id']}").get_json()["data"]["path"] == "/uffici/scuola"
    assert "page.slug_changed" in actions(app)
    assert _redirects(app) == set()  # pagine mai pubblicate: nessun reindirizzamento


def test_stale_version_is_409_with_current_state(login_as: LoginAs) -> None:
    client, editor = login_as("editor")
    page = create_page(client)
    assert _patch(client, page["id"], slug="nuovo").status_code == 200
    response = client.patch(f"{PAGES}/{page['id']}", json={"version": 1, "slug": "altro"})
    assert (response.status_code, error_code(response)) == (409, "version_conflict")
    info = response.get_json()["error"]["details"]
    assert info["current_version"] == 2
    assert info["updated_by"] == editor.id


def test_move_under_another_parent_and_back_to_top(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    a, b = create_page(client, "A"), create_page(client, "B")
    moved = _patch(client, b["id"], parent_id=a["id"]).get_json()["data"]
    assert (moved["parent_id"], moved["path"]) == (a["id"], "/a/b")
    top = _patch(client, b["id"], parent_id=None).get_json()["data"]
    assert (top["parent_id"], top["path"]) == (None, "/b")


def test_move_rejects_cycles_depth_and_taken_paths(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    chain = _chain(client, 3)
    cycle = _patch(client, chain[0]["id"], parent_id=chain[2]["id"])
    assert (cycle.status_code, error_code(cycle)) == (422, "cycle")
    other = _chain(client, 2)  # sposta un ramo di 3 livelli sotto un ramo di 2: 5 livelli
    deep = _patch(client, chain[0]["id"], parent_id=other[1]["id"])
    assert (deep.status_code, error_code(deep)) == (422, "too_deep")
    create_page(client, "Livello 2", slug="livello-2")
    taken = _patch(client, chain[1]["id"], parent_id=None)
    assert (taken.status_code, error_code(taken)) == (409, "path_taken")
    home = create_page(client, "Home", layout="home", slug="")
    under_home = _patch(client, chain[0]["id"], parent_id=home["id"])
    assert error_code(under_home) == "home_has_no_children"
    home_slug = _patch(client, home["id"], slug="casa")
    assert error_code(home_slug) == "home_is_fixed"


def test_online_pages_need_publish_permission_to_move(app: Flask, login_as: LoginAs) -> None:
    publisher, _ = login_as("editor", can_publish=True)
    editor, _ = login_as("editor")
    parent = create_page(publisher, "Servizi")
    child = create_page(publisher, "Scuola", parent_id=parent["id"])
    assert publish(publisher, child["id"]).status_code == 200
    # il genitore non è online, ma spostarlo cambia l'indirizzo della figlia online
    assert _patch(editor, parent["id"], slug="uffici").status_code == 403
    assert _patch(publisher, parent["id"], slug="uffici").status_code == 200
    assert _redirects(app) == {("it", "/servizi/scuola", child["id"])}


def test_redirects_follow_the_page_and_never_shadow_a_live_page(
    app: Flask, login_as: LoginAs
) -> None:
    client, _ = login_as("admin")
    page = create_page(client, "Orari")
    assert publish(client, page["id"]).status_code == 200
    _patch(client, page["id"], slug="orari-apertura")
    _patch(client, page["id"], slug="aperture")
    assert _redirects(app) == {("it", "/orari", page["id"]), ("it", "/orari-apertura", page["id"])}
    _patch(client, page["id"], slug="orari")  # torna all'indirizzo di prima
    assert _redirects(app) == {
        ("it", "/orari-apertura", page["id"]),
        ("it", "/aperture", page["id"]),
    }
    create_page(client, "Aperture")  # una pagina vera prende il posto del vecchio indirizzo
    assert _redirects(app) == {("it", "/orari-apertura", page["id"])}


# --- Riordino ----------------------------------------------------------------


def test_reorder_children(app: Flask, login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    a, b, c = (create_page(client, t)["id"] for t in ("A", "B", "C"))
    response = client.post(
        f"{PAGES}/reorder", json={"parent_id": None, "locale": "it", "ids": [c, a, b]}
    )
    assert response.status_code == 200
    tree = client.get(f"{PAGES}/tree?locale=it").get_json()["data"]
    assert [n["id"] for n in tree] == [c, a, b]
    assert "page.reordered" in actions(app)
    wrong = client.post(f"{PAGES}/reorder", json={"parent_id": None, "locale": "it", "ids": [c, a]})
    assert (wrong.status_code, error_code(wrong)) == (422, "reorder_mismatch")


# --- Cestino -----------------------------------------------------------------


def test_trash_and_restore(app: Flask, login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    page = create_page(client)
    response = trash(client, page["id"])
    assert response.status_code == 200
    assert response.get_json()["data"]["deleted_at"] is not None
    assert client.get(f"{PAGES}/{page['id']}").status_code == 404
    assert [p["id"] for p in client.get(f"{PAGES}/trash").get_json()["data"]] == [page["id"]]
    restored = restore(client, page["id"])
    assert restored.status_code == 200
    assert restored.get_json()["data"]["status"] == "draft"
    assert {"page.trashed", "page.restored"} <= set(actions(app))


def test_trashed_page_frees_its_path(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    old = create_page(client)
    trash(client, old["id"])
    assert create_page(client)["slug"] == "chi-siamo"
    response = restore(client, old["id"])
    assert (response.status_code, error_code(response)) == (409, "path_taken")


def test_trash_rules(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    parent = create_page(client, "Servizi")
    child = create_page(client, "Scuola", parent_id=parent["id"])
    home = create_page(client, "Home", layout="home", slug="")
    with_children = trash(client, parent["id"])
    assert (with_children.status_code, error_code(with_children)) == (409, "has_children")
    protected = trash(client, home["id"])
    assert (protected.status_code, error_code(protected)) == (409, "home_protected")
    assert trash(client, child["id"]).status_code == 200
    assert trash(client, parent["id"]).status_code == 200
    restore_child = restore(client, child["id"])
    assert (restore_child.status_code, error_code(restore_child)) == (409, "parent_trashed")


def test_trashing_an_online_page_needs_publish_permission(login_as: LoginAs) -> None:
    publisher, _ = login_as("editor", can_publish=True)
    editor, _ = login_as("editor")
    page = create_page(publisher)
    assert publish(publisher, page["id"]).status_code == 200
    assert trash(editor, page["id"]).status_code == 403
    trashed = trash(publisher, page["id"])
    assert trashed.status_code == 200
    assert trashed.get_json()["data"]["status"] == "draft"  # si recupera come bozza
    assert trashed.get_json()["data"]["published_at"] is None


# --- Regressioni dalla review ECC della Fase 2 -------------------------------------------


def test_trash_with_stale_version_is_409(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    page = create_page(client)
    _patch(client, page["id"], slug="altro")
    response = trash(client, page["id"], version=page["version"])
    assert (response.status_code, error_code(response)) == (409, "version_conflict")


def test_full_path_longer_than_the_column_is_422(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    parent: dict[str, Any] | None = None
    for level in range(3):
        extra = {"parent_id": parent["id"]} if parent else {}
        parent = create_page(client, f"L{level}", slug=f"{level}" + "a" * 79, **extra)
    assert parent is not None
    response = client.post(
        PAGES, json={"title": "x", "layout": "page", "slug": "b" * 80, "parent_id": parent["id"]}
    )
    assert (response.status_code, error_code(response)) == (422, "path_too_long")


def test_editor_cannot_move_a_scheduled_page(login_as: LoginAs) -> None:
    publisher, _ = login_as("admin")
    editor, _ = login_as("editor")
    page = create_page(publisher)
    when = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    body = {"draft_version": 1, "publish_at": when}
    assert publisher.post(f"{PAGES}/{page['id']}/schedule", json=body).status_code == 200
    assert _patch(editor, page["id"], slug="altro").status_code == 403


def test_titles_stay_on_one_line(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    assert create_page(client, "Prima riga\nseconda\triga")["title"] == "Prima riga seconda riga"


def test_tree_reports_truncation(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    create_page(client)
    assert client.get(f"{PAGES}/tree").get_json()["meta"] == {"truncated": False}
