"""Fixture comuni. I temi di prova vengono creati solo in cartelle temporanee."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.extensions import db
from tests.helpers import UserRef, api_client, login, make_user

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_THEME_DATA: dict[str, Any] = json.loads(
    (ROOT / "themes" / "default" / "theme.json").read_text(encoding="utf-8")
)

MakeTheme = Callable[..., Path]
APP_ENV_VARS = (
    "APP_ENV",
    "SECRET_KEY",
    "DATABASE_URL",
    "THEMES_DIR",
    "ACTIVE_THEME",
    "MAX_UPLOAD_MB",
    "TRUSTED_PROXY_COUNT",
)
LoginAs = Callable[..., tuple[FlaskClient, UserRef]]


@pytest.fixture
def app() -> Iterator[Flask]:
    """App di test con database in memoria. Il contesto NON resta attivo durante le richieste
    (altrimenti `g` e l'utente loggato verrebbero condivisi tra richieste diverse)."""
    application = create_app("testing")
    with application.app_context():
        db.create_all()  # ammesso solo nei test (CLAUDE.md); la parità con Alembic è testata
    yield application


@pytest.fixture
def api(app: Flask) -> FlaskClient:
    return api_client(app)


@pytest.fixture
def login_as(app: Flask) -> LoginAs:
    counter = iter(range(1, 1000))

    def _login(role: str, **kwargs: Any) -> tuple[FlaskClient, UserRef]:
        user = make_user(app, f"{role}{next(counter)}@example.ch", role, **kwargs)
        client = api_client(app)
        assert login(client, user.email).status_code == 200
        return client, user

    return _login


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """I test non dipendono mai dalle variabili d'ambiente della shell o della CI."""
    for var in APP_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


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
