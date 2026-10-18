"""Tabelle della libreria media (D-74, D-76, D-80, D-82)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from flask import Flask
from flask_migrate import upgrade
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from app.models.media import Media, MediaFolder

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def ctx(app: Flask) -> Iterator[None]:
    with app.app_context():
        yield


def _media(n: int = 1, **extra: object) -> Media:
    values: dict[str, object] = {
        "storage_key": f"{n:032x}",
        "kind": "image",
        "mime": "image/png",
        "ext": "png",
        "original_name": "foto.png",
        "search_key": "foto.png",
        "size_bytes": 100,
        "sha256": f"{n:064x}",
        "width": 10,
        "height": 10,
        "variants_json": {},
        **extra,
    }
    return Media(**values)


def test_media_defaults(ctx: None) -> None:
    media = _media()
    db.session.add(media)
    db.session.commit()
    assert (media.alt, media.focal_x, media.focal_y, media.file_rev, media.version) == (
        "",
        50,
        50,
        1,
        1,
    )


@pytest.mark.parametrize("field", ["sha256", "storage_key"])
def test_unique_fields(ctx: None, field: str) -> None:
    first, second = _media(1), _media(2)
    setattr(second, field, getattr(first, field))
    db.session.add_all([first, second])
    with pytest.raises(IntegrityError):
        db.session.commit()


@pytest.mark.parametrize("extra", [{"focal_x": 101}, {"focal_y": -1}, {"kind": "video"}])
def test_checks(ctx: None, extra: dict[str, Any]) -> None:
    db.session.add(_media(1, **extra))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_folder_names_unique_per_parent_also_at_root(ctx: None) -> None:
    db.session.add_all(
        [MediaFolder(name="Foto", name_key="foto"), MediaFolder(name="FOTO", name_key="foto")]
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    parent = MediaFolder(name="Eventi", name_key="eventi")
    db.session.add(parent)
    db.session.flush()
    db.session.add_all(
        [
            MediaFolder(name="2026", name_key="2026", parent_id=parent.id),
            MediaFolder(name="2026", name_key="2026"),  # stesso nome ma in un'altra cartella
        ]
    )
    db.session.commit()


def test_migration_creates_the_partial_index(tmp_path: Path) -> None:
    uri = f"sqlite:///{(tmp_path / 'cms.db').as_posix()}"
    app = create_app("testing", overrides={"SQLALCHEMY_DATABASE_URI": uri})
    with app.app_context():
        upgrade(directory=str(ROOT / "migrations"))
        sql = db.session.execute(
            text("SELECT sql FROM sqlite_master WHERE name = 'uq_media_folders_root_name'")
        ).scalar_one()
    assert "WHERE parent_id IS NULL" in " ".join(sql.split())
