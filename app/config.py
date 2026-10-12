"""Configurazione per ambiente, scelto con APP_ENV (D-19)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ACTIVE_THEME = "default"
# Valore di .env.example: serve solo per rifiutarlo in produzione.
EXAMPLE_SECRET_KEY = "cambia-questa-chiave"  # noqa: S105
MIN_SECRET_KEY_LENGTH = 32
DEFAULT_MAX_UPLOAD_MB = 15
BYTES_PER_MB = 1024 * 1024


class ConfigError(RuntimeError):
    """Configurazione mancante o non sicura: l'app non deve partire."""


def _common(environ: Mapping[str, str]) -> dict[str, Any]:
    max_upload_mb = int(environ.get("MAX_UPLOAD_MB", str(DEFAULT_MAX_UPLOAD_MB)))
    return {
        "THEMES_DIR": Path(environ.get("THEMES_DIR", str(PROJECT_ROOT / "themes"))).resolve(),
        "ACTIVE_THEME": environ.get("ACTIVE_THEME", DEFAULT_ACTIVE_THEME),
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "MAX_CONTENT_LENGTH": max_upload_mb * BYTES_PER_MB,
    }


def _development(environ: Mapping[str, str]) -> dict[str, Any]:
    default_db = f"sqlite:///{(PROJECT_ROOT / 'data' / 'cms.db').as_posix()}"
    return {
        "DEBUG": True,
        "TESTING": False,
        "SECRET_KEY": environ.get("SECRET_KEY", "dev-chiave-non-sicura"),
        "SQLALCHEMY_DATABASE_URI": environ.get("DATABASE_URL", default_db),
        "SESSION_COOKIE_SECURE": False,
    }


def _testing(_environ: Mapping[str, str]) -> dict[str, Any]:
    # I test non leggono mai il database dall'ambiente: niente rischi su dati reali.
    return {
        "DEBUG": False,
        "TESTING": True,
        "SECRET_KEY": "test-chiave-non-sicura",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SESSION_COOKIE_SECURE": False,
    }


def _production(environ: Mapping[str, str]) -> dict[str, Any]:
    secret_key = environ.get("SECRET_KEY", "")
    if secret_key == EXAMPLE_SECRET_KEY or len(secret_key) < MIN_SECRET_KEY_LENGTH:
        raise ConfigError(
            f"SECRET_KEY mancante o debole: servono {MIN_SECRET_KEY_LENGTH}+ caratteri casuali"
        )
    database_url = environ.get("DATABASE_URL")
    if not database_url:
        raise ConfigError("DATABASE_URL mancante in produzione")
    return {
        "DEBUG": False,
        "TESTING": False,
        "SECRET_KEY": secret_key,
        "SQLALCHEMY_DATABASE_URI": database_url,
        "SESSION_COOKIE_SECURE": True,
    }


_ENVIRONMENTS: dict[str, Callable[[Mapping[str, str]], dict[str, Any]]] = {
    "development": _development,
    "testing": _testing,
    "production": _production,
}


def build_config(name: str, environ: Mapping[str, str]) -> dict[str, Any]:
    """Restituisce la configurazione Flask per l'ambiente `name`."""
    try:
        specific = _ENVIRONMENTS[name]
    except KeyError:
        valid = ", ".join(sorted(_ENVIRONMENTS))
        raise ConfigError(f"Ambiente sconosciuto: {name!r} (validi: {valid})") from None
    return {**_common(environ), **specific(environ)}
