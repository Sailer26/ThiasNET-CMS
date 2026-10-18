"""Archivio dei file caricati (D-74): solo in MEDIA_ROOT, solo con nomi generati dal CMS."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask

from app.services import media_storage
from app.services.media_storage import MediaStorageError

KEY = "0123456789abcdef0123456789abcdef"


@pytest.fixture
def ctx(app: Flask) -> Iterator[Path]:
    with app.app_context():
        yield Path(app.config["MEDIA_ROOT"])


def test_files_go_under_a_generated_key(ctx: Path) -> None:
    media_storage.put(KEY, "r1-master.png", b"dati")
    path = ctx / "01" / KEY / "r1-master.png"
    assert path.read_bytes() == b"dati"
    assert media_storage.path_for(KEY, "r1-master.png") == path.resolve()


def test_new_keys_are_random_hex() -> None:
    first, second = media_storage.new_key(), media_storage.new_key()
    assert first != second and len(first) == 32 and int(first, 16) >= 0


@pytest.mark.parametrize(
    ("key", "name"),
    [
        ("../" + KEY[3:], "r1-master.png"),
        (KEY.upper(), "r1-master.png"),
        (KEY, "../../themes/default/theme.json"),
        (KEY, "/etc/passwd"),
        (KEY, "r1-master.html"),
        (KEY, "evil.php"),
        (KEY, "r1-master.png\\..\\x"),
        (KEY, "foto vacanze.jpg"),
    ],
)
def test_only_generated_names_are_accepted(ctx: Path, key: str, name: str) -> None:
    with pytest.raises(MediaStorageError):
        media_storage.put(key, name, b"x")


def test_existing_files_are_never_overwritten(ctx: Path) -> None:
    media_storage.put(KEY, "r1.pdf", b"prima")
    with pytest.raises(MediaStorageError):
        media_storage.put(KEY, "r1.pdf", b"dopo")
    assert media_storage.path_for(KEY, "r1.pdf").read_bytes() == b"prima"


def test_discard_removes_files_and_the_empty_folder(ctx: Path) -> None:
    media_storage.put(KEY, "r1-master.png", b"a")
    media_storage.put(KEY, "r1-card-640.webp", b"b")
    media_storage.discard(KEY, ["r1-master.png", "r1-card-640.webp", "r1-assente-1.webp"])
    assert not (ctx / "01" / KEY).exists()


def test_symlinks_leaving_the_root_are_refused(ctx: Path, tmp_path: Path) -> None:
    outside = tmp_path / "fuori"
    outside.mkdir()
    (ctx / "01").mkdir(parents=True)
    try:
        (ctx / "01" / KEY).symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink non consentiti su questo sistema")
    with pytest.raises(MediaStorageError):
        media_storage.put(KEY, "r1-master.png", b"x")
    assert not any(outside.iterdir())
