"""Tabelle delle pagine (D-38): vincoli, indici parziali, cascate e migrazione 0004."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from flask import Flask
from flask_migrate import downgrade, upgrade
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from app.models.page import Block, Page, PageDraft, PageRedirect, PageRevision

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = str(ROOT / "migrations")


def _page(slug: str = "chi-siamo", **extra: object) -> Page:
    values: dict[str, object] = {
        "locale": "it",
        "translation_group": str(uuid.uuid4()),  # D-151: una pagina per lingua nel gruppo
        "slug": slug,
        "path": f"/{slug}",
        "title": "Chi siamo",
        "layout": "page",
        "seo_json": {},
        **extra,
    }
    return Page(**values)


def _block(page_id: int, uid: str = "a" * 32, **extra: object) -> Block:
    values: dict[str, object] = {
        "page_id": page_id,
        "uid": uid,
        "zone": "main",
        "type": "text",
        "data_json": {"body": "<p>x</p>"},
        "sort": 0,
        **extra,
    }
    return Block(**values)


def _count(model: type) -> int:
    return db.session.execute(select(func.count()).select_from(model)).scalar_one()


@pytest.fixture
def ctx(app: Flask) -> Iterator[None]:
    with app.app_context():
        yield


def test_page_defaults(ctx: None) -> None:
    page = _page()
    db.session.add(page)
    db.session.commit()
    assert (page.status, page.version, page.sort) == ("draft", 1, 0)
    assert page.deleted_at is None
    assert page.created_at.tzinfo is not None


def test_page_status_is_checked(ctx: None) -> None:
    db.session.add(_page(status="online"))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_block_type_is_checked(ctx: None) -> None:
    page = _page()
    db.session.add(page)
    db.session.flush()
    db.session.add(_block(page.id, type="carousel"))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_revision_kind_is_checked(ctx: None) -> None:
    page = _page()
    db.session.add(page)
    db.session.flush()
    db.session.add(PageRevision(page_id=page.id, kind="autosave", snapshot_json={}))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_path_unique_per_locale_among_live_pages(ctx: None) -> None:
    db.session.add_all([_page(), _page(locale="de")])
    db.session.commit()
    db.session.add(_page())
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_trashed_pages_do_not_hold_their_path(ctx: None) -> None:
    db.session.add(_page(deleted_at=datetime.now(UTC)))
    db.session.commit()
    db.session.add(_page())
    db.session.commit()
    assert _count(Page) == 2


def test_block_uid_unique_per_page(ctx: None) -> None:
    page = _page()
    db.session.add(page)
    db.session.flush()
    db.session.add_all([_block(page.id), _block(page.id, sort=1)])
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_only_one_pending_schedule_per_page(ctx: None) -> None:
    page = _page()
    db.session.add(page)
    db.session.flush()
    db.session.add_all(
        [
            PageRevision(page_id=page.id, kind="published", snapshot_json={}),
            PageRevision(page_id=page.id, kind="published", snapshot_json={}),
            PageRevision(page_id=page.id, kind="scheduled", snapshot_json={}),
        ]
    )
    db.session.commit()
    db.session.add(PageRevision(page_id=page.id, kind="scheduled", snapshot_json={}))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_deleting_a_page_cascades_to_its_content(ctx: None) -> None:
    page = _page()
    db.session.add(page)
    db.session.flush()
    db.session.add_all(
        [
            _block(page.id),
            PageDraft(page_id=page.id, data_json={}),
            PageRevision(page_id=page.id, kind="published", snapshot_json={}),
            PageRedirect(page_id=page.id, locale="it", from_path="/vecchio"),
        ]
    )
    db.session.commit()
    db.session.execute(text("DELETE FROM pages"))
    db.session.commit()
    assert [_count(m) for m in (Block, PageDraft, PageRevision, PageRedirect)] == [0, 0, 0, 0]


def test_parent_with_children_cannot_be_deleted(ctx: None) -> None:
    parent = _page()
    db.session.add(parent)
    db.session.flush()
    db.session.add(_page("team", path="/chi-siamo/team", parent_id=parent.id))
    db.session.commit()
    with pytest.raises(IntegrityError):
        db.session.execute(text("DELETE FROM pages WHERE id = :id"), {"id": parent.id})
        db.session.commit()


def test_redirect_source_unique_per_locale(ctx: None) -> None:
    page = _page()
    db.session.add(page)
    db.session.flush()
    db.session.add_all(
        [
            PageRedirect(page_id=page.id, locale="it", from_path="/vecchio"),
            PageRedirect(page_id=page.id, locale="it", from_path="/vecchio"),
        ]
    )
    with pytest.raises(IntegrityError):
        db.session.commit()


# --- Migrazione ----------------------------------------------------------------


def _migrated_app(tmp_path: Path) -> Flask:
    uri = f"sqlite:///{(tmp_path / 'cms.db').as_posix()}"
    return create_app("testing", overrides={"SQLALCHEMY_DATABASE_URI": uri})


def test_migration_creates_partial_indexes(tmp_path: Path) -> None:
    """compare_metadata non guarda le condizioni degli indici parziali: le verifichiamo qui."""
    app = _migrated_app(tmp_path)
    with app.app_context():
        upgrade(directory=MIGRATIONS)
        rows = db.session.execute(
            text("SELECT name, sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")
        ).all()
    sql = {name: " ".join(statement.split()) for name, statement in rows}
    assert "WHERE deleted_at IS NULL" in sql["uq_pages_locale_path"]
    assert "WHERE kind = 'scheduled'" in sql["uq_page_revisions_scheduled"]


def test_migration_downgrades_cleanly(tmp_path: Path) -> None:
    app = _migrated_app(tmp_path)
    with app.app_context():
        upgrade(directory=MIGRATIONS)
        downgrade(directory=MIGRATIONS, revision="0003_server_defaults")
        tables = set(
            db.session.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'"))
            .scalars()
            .all()
        )
        assert not tables & {"pages", "blocks", "page_revisions", "page_drafts", "page_redirects"}
        upgrade(directory=MIGRATIONS)
