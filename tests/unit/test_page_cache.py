"""Cache delle pagine (D-54): in memoria per processo, invalidata dal contatore nel database."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient
from flask_migrate import upgrade
from sqlalchemy import text

from app import create_app
from app.extensions import db
from app.services import page_cache
from app.services.page_cache import PageCache
from app.services.render import Renderer
from tests.conftest import LoginAs
from tests.pages_helpers import (
    PAGES,
    create_page,
    doc,
    page_version,
    publish,
    put_draft,
    text_block,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def ctx(app: Flask) -> Iterator[None]:
    with app.app_context():
        yield


# --- Unità ------------------------------------------------------------------------


def test_hit_and_miss() -> None:
    cache = PageCache(max_entries=10, max_bytes=1000)
    assert cache.get(("it", "/a"), generation=1) is None
    cache.put(("it", "/a"), "<p>a</p>", generation=1)
    assert cache.get(("it", "/a"), generation=1) == "<p>a</p>"


def test_new_generation_empties_the_cache() -> None:
    cache = PageCache(max_entries=10, max_bytes=1000)
    cache.put(("it", "/a"), "<p>a</p>", generation=1)
    assert cache.get(("it", "/a"), generation=2) is None
    cache.put(("it", "/b"), "<p>b</p>", generation=1)  # risposta vecchia arrivata tardi
    assert cache.get(("it", "/b"), generation=2) is None


def test_least_recently_used_is_evicted_by_count() -> None:
    cache = PageCache(max_entries=2, max_bytes=1000)
    cache.put(("it", "/a"), "a", generation=1)
    cache.put(("it", "/b"), "b", generation=1)
    cache.get(("it", "/a"), generation=1)  # /a usata di recente
    cache.put(("it", "/c"), "c", generation=1)
    assert cache.get(("it", "/b"), generation=1) is None
    assert cache.get(("it", "/a"), generation=1) == "a"


def test_eviction_by_size_and_oversized_pages_are_skipped() -> None:
    cache = PageCache(max_entries=10, max_bytes=10)
    cache.put(("it", "/a"), "x" * 6, generation=1)
    cache.put(("it", "/b"), "y" * 6, generation=1)
    assert cache.get(("it", "/a"), generation=1) is None
    cache.put(("it", "/enorme"), "z" * 50, generation=1)
    assert cache.get(("it", "/enorme"), generation=1) is None
    assert cache.get(("it", "/b"), generation=1) == "y" * 6


def test_generation_lives_in_the_database(ctx: None) -> None:
    assert page_cache.current_generation() == 0  # nei test la riga non esiste ancora
    page_cache.mark_changed()
    page_cache.mark_changed()
    db.session.commit()
    assert page_cache.current_generation() == 2


def test_two_workers_see_the_same_invalidation(ctx: None) -> None:
    worker_a, worker_b = PageCache(10, 1000), PageCache(10, 1000)
    generation = page_cache.current_generation()
    worker_a.put(("it", "/a"), "vecchia", generation)
    worker_b.put(("it", "/a"), "vecchia", generation)
    page_cache.mark_changed()
    db.session.commit()
    fresh = page_cache.current_generation()
    assert worker_a.get(("it", "/a"), fresh) is None
    assert worker_b.get(("it", "/a"), fresh) is None


def test_migration_creates_the_single_row(tmp_path: Path) -> None:
    uri = f"sqlite:///{(tmp_path / 'cms.db').as_posix()}"
    app = create_app("testing", overrides={"SQLALCHEMY_DATABASE_URI": uri})
    with app.app_context():
        upgrade(directory=str(ROOT / "migrations"))
        rows = db.session.execute(text("SELECT id, cache_generation FROM site_state")).all()
    assert [tuple(r) for r in rows] == [(1, 0)]


# --- Sito ---------------------------------------------------------------------------


@pytest.fixture
def admin(login_as: LoginAs) -> FlaskClient:
    client, _ = login_as("admin")
    return client


def _online(client: FlaskClient, title: str, body: str) -> dict[str, Any]:
    page = create_page(client, title)
    put_draft(
        client, page["id"], doc(title=title, zones={"main": [text_block(1, body)], "sidebar": []})
    )
    assert publish(client, page["id"]).status_code == 200
    return page


@pytest.fixture
def renders(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    real = Renderer.render_page

    def counting(self: Renderer, context: Any) -> str:
        calls.append(context.page.path)
        return real(self, context)

    monkeypatch.setattr(Renderer, "render_page", counting)
    return calls


def _generation(app: Flask) -> int:
    with app.app_context():
        return page_cache.current_generation()


def test_second_visit_comes_from_the_cache(
    app: Flask, admin: FlaskClient, renders: list[str]
) -> None:
    _online(admin, "Chi siamo", "<p>Prima</p>")
    visitor = app.test_client()
    assert "Prima" in visitor.get("/chi-siamo").get_data(as_text=True)
    assert "Prima" in visitor.get("/chi-siamo").get_data(as_text=True)
    assert renders == ["/chi-siamo"]


def test_publishing_shows_the_new_content(app: Flask, admin: FlaskClient) -> None:
    page = _online(admin, "Chi siamo", "<p>Prima</p>")
    visitor = app.test_client()
    visitor.get("/chi-siamo")
    zones = {"main": [text_block(1, "<p>Dopo</p>")], "sidebar": []}
    put_draft(admin, page["id"], doc(zones=zones), version=0)
    assert "Prima" in visitor.get("/chi-siamo").get_data(as_text=True)  # l'autosave non pubblica
    publish(admin, page["id"])
    assert "Dopo" in visitor.get("/chi-siamo").get_data(as_text=True)


def test_every_visible_change_bumps_the_generation(app: Flask, admin: FlaskClient) -> None:
    first = _online(admin, "Primo", "<p>1</p>")
    second = _online(admin, "Secondo", "<p>2</p>")

    def bumps(action: Any) -> bool:
        before = _generation(app)
        action()
        return _generation(app) > before

    assert bumps(lambda: _online(admin, "Terzo", "<p>3</p>"))
    assert bumps(
        lambda: admin.patch(
            f"{PAGES}/{first['id']}",
            json={"version": page_version(admin, first["id"]), "slug": "uno"},
        )
    )
    assert bumps(
        lambda: admin.post(
            f"{PAGES}/reorder",
            json={
                "parent_id": None,
                "locale": "it",
                "ids": [second["id"], first["id"], second["id"] + 1],
            },
        )
    )
    assert bumps(
        lambda: admin.post(
            f"{PAGES}/{second['id']}/unpublish", json={"version": page_version(admin, second["id"])}
        )
    )
    assert bumps(
        lambda: admin.delete(
            f"{PAGES}/{first['id']}", json={"version": page_version(admin, first["id"])}
        )
    )
    assert not bumps(lambda: put_draft(admin, second["id"], doc(title="Solo bozza")))


def test_not_found_pages_are_not_cached(app: Flask, renders: list[str]) -> None:
    visitor = app.test_client()
    assert visitor.get("/manca").status_code == 404
    assert visitor.get("/manca").status_code == 404
    assert renders == []  # la 404 usa render_not_found, mai la cache delle pagine
