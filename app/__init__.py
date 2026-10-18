"""ThiasNET CMS — application factory."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from flask import Flask

from app.api import register_error_handlers, register_response_headers
from app.api.admin import bp as admin_api
from app.cli import register_cli
from app.config import PROJECT_ROOT, build_config
from app.database import ensure_sqlite_directory  # importarlo registra anche i PRAGMA SQLite
from app.extensions import db, migrate
from app.panel import bp as panel
from app.public import register_public
from app.security import init_security
from app.services.theme import ACTIVE_THEME_KEY, Theme, active_theme, load_theme

__all__ = ["ACTIVE_THEME_KEY", "create_app", "get_theme"]
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"


def _require_webp() -> None:
    """D-84: senza WebP le varianti non si possono creare: meglio non partire."""
    from PIL import features

    if not features.check("webp"):
        raise RuntimeError("Pillow senza supporto WebP: reinstallare Pillow con WebP")


def create_app(config_name: str | None = None, overrides: Mapping[str, Any] | None = None) -> Flask:
    """Crea l'app. Se il tema attivo non è valido solleva ThemeValidationError e non parte."""
    app = Flask(__name__)
    app.config.from_mapping(build_config(config_name or os.environ.get("APP_ENV"), os.environ))
    if overrides:
        app.config.from_mapping(overrides)

    _require_webp()
    app.extensions[ACTIVE_THEME_KEY] = load_theme(
        Path(app.config["THEMES_DIR"]), app.config["ACTIVE_THEME"]
    )

    ensure_sqlite_directory(app.config["SQLALCHEMY_DATABASE_URI"])
    db.init_app(app)
    migrate.init_app(app, db, directory=str(MIGRATIONS_DIR))
    init_security(app)
    register_error_handlers(app)
    register_response_headers(app)
    app.register_blueprint(admin_api)
    app.register_blueprint(panel)  # prima del sito: /admin/... non è una pagina (D-87)
    register_public(app)
    register_cli(app)
    return app


def get_theme() -> Theme:
    """Tema attivo dell'app corrente (sola lettura)."""
    return active_theme()
