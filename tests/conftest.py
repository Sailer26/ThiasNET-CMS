"""Fixture comuni. I temi di prova vengono creati solo in cartelle temporanee."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_THEME_DATA: dict[str, Any] = json.loads(
    (ROOT / "themes" / "default" / "theme.json").read_text(encoding="utf-8")
)

MakeTheme = Callable[..., Path]


@pytest.fixture
def theme_data() -> dict[str, Any]:
    """Copia modificabile del theme.json del tema default."""
    return copy.deepcopy(DEFAULT_THEME_DATA)


@pytest.fixture
def make_theme(tmp_path: Path) -> MakeTheme:
    """Crea `tmp_path/themes/<name>/theme.json` e restituisce la cartella `themes`."""
    themes_dir = tmp_path / "themes"

    def _make(
        data: dict[str, Any] | str,
        name: str = "demo",
        thumbnails: Iterable[str] = (),
    ) -> Path:
        theme_dir = themes_dir / name
        (theme_dir / "assets").mkdir(parents=True, exist_ok=True)
        content = data if isinstance(data, str) else json.dumps({**data, "name": name})
        (theme_dir / "theme.json").write_text(content, encoding="utf-8")
        for thumb in thumbnails:
            target = theme_dir / "assets" / thumb
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"thumbnail")
        return themes_dir

    return _make
