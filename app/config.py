"""Configurazione per ambiente, scelto con APP_ENV (D-19)."""

from __future__ import annotations

import secrets
from collections.abc import Callable, Mapping
from datetime import timedelta
from pathlib import Path
from typing import Any

from argon2.profiles import RFC_9106_LOW_MEMORY

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ACTIVE_THEME = "default"
# Valore di .env.example: serve solo per rifiutarlo in produzione.
EXAMPLE_SECRET_KEY = "cambia-questa-chiave"  # noqa: S105
MIN_SECRET_KEY_LENGTH = 32
DEFAULT_MAX_UPLOAD_MB = 15
BYTES_PER_MB = 1024 * 1024


class ConfigError(RuntimeError):
    """Configurazione mancante o non sicura: l'app non deve partire."""


SESSION_LIFETIME = timedelta(hours=12)  # D-27: niente "ricordami", sessione che si rinnova
PRODUCTION_PROXY_COUNT = 1  # Caddy davanti a gunicorn (D-34)


def _int_env(environ: Mapping[str, str], name: str, default: int, minimum: int) -> int:
    raw = environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} deve essere un intero, non {raw!r}") from None
    if value < minimum:
        raise ConfigError(f"{name} deve essere almeno {minimum}, non {value}")
    return value


def _common(environ: Mapping[str, str]) -> dict[str, Any]:
    max_upload_mb = _int_env(environ, "MAX_UPLOAD_MB", DEFAULT_MAX_UPLOAD_MB, minimum=1)
    return {
        "THEMES_DIR": Path(environ.get("THEMES_DIR", str(PROJECT_ROOT / "themes"))).resolve(),
        "ACTIVE_THEME": environ.get("ACTIVE_THEME", DEFAULT_ACTIVE_THEME),
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "MAX_CONTENT_LENGTH": max_upload_mb * BYTES_PER_MB,
        # Sessione e cookie
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "PERMANENT_SESSION_LIFETIME": SESSION_LIFETIME,
        "SESSION_REFRESH_EACH_REQUEST": True,
        "REMEMBER_COOKIE_HTTPONLY": True,
        "REMEMBER_COOKIE_SAMESITE": "Lax",
        # CSRF (D-23): il token vive quanto la sessione, arriva alla SPA via header.
        "WTF_CSRF_TIME_LIMIT": None,
        "TRUSTED_PROXY_COUNT": _int_env(environ, "TRUSTED_PROXY_COUNT", 0, minimum=0),
        # Argon2id: parametri RFC 9106 "low memory" (default di argon2-cffi).
        "ARGON2_TIME_COST": RFC_9106_LOW_MEMORY.time_cost,
        "ARGON2_MEMORY_COST": RFC_9106_LOW_MEMORY.memory_cost,
        "ARGON2_PARALLELISM": RFC_9106_LOW_MEMORY.parallelism,
    }


def _development(environ: Mapping[str, str]) -> dict[str, Any]:
    default_db = f"sqlite:///{(PROJECT_ROOT / 'data' / 'cms.db').as_posix()}"
    return {
        "DEBUG": True,
        "TESTING": False,
        # Senza SECRET_KEY si usa una chiave casuale: le sessioni durano fino al riavvio.
        "SECRET_KEY": environ.get("SECRET_KEY") or secrets.token_urlsafe(MIN_SECRET_KEY_LENGTH),
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
        # Hash velocissimi solo nei test: Argon2 vero costerebbe secondi per ogni login.
        "ARGON2_TIME_COST": 1,
        "ARGON2_MEMORY_COST": 64,
        "ARGON2_PARALLELISM": 1,
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
        # __Host-: solo HTTPS, niente Domain, Path=/ (non sovrascrivibile da sottodomini).
        "SESSION_COOKIE_NAME": "__Host-session",
        "REMEMBER_COOKIE_NAME": "__Host-remember_token",
        "REMEMBER_COOKIE_SECURE": True,
        "TRUSTED_PROXY_COUNT": _int_env(
            environ, "TRUSTED_PROXY_COUNT", PRODUCTION_PROXY_COUNT, minimum=0
        ),
    }


_ENVIRONMENTS: dict[str, Callable[[Mapping[str, str]], dict[str, Any]]] = {
    "development": _development,
    "testing": _testing,
    "production": _production,
}


def build_config(name: str | None, environ: Mapping[str, str]) -> dict[str, Any]:
    """Restituisce la configurazione Flask per l'ambiente `name` (di solito APP_ENV).

    Fail-closed: senza ambiente esplicito l'app non parte, così un deploy che dimentica
    APP_ENV non finisce in modalità sviluppo.
    """
    if not name:
        raise ConfigError("APP_ENV mancante: impostare development, testing o production")
    try:
        specific = _ENVIRONMENTS[name]
    except KeyError:
        valid = ", ".join(sorted(_ENVIRONMENTS))
        raise ConfigError(f"Ambiente sconosciuto: {name!r} (validi: {valid})") from None
    from app.config_site import site_config  # importa ConfigError da qui: niente ciclo

    return {**_common(environ), **specific(environ), **site_config(name, environ)}
