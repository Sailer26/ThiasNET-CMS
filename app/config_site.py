"""Configurazione del sito pubblico: indirizzo, email, statistiche, cache (D-57, D-62, D-66).

Fino alla Fase 6 queste impostazioni le decide Thias al deploy, in `.env`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from app.config import ConfigError

SITE_DEFAULTS = {
    "development": "http://localhost:5000",
    "testing": "https://www.example.ch",
}
MAIL_BACKENDS = {"development": "console", "testing": "memory", "production": "smtp"}
SMTP_SECURITY_MODES = frozenset({"starttls", "ssl", "none"})
DEFAULT_SMTP_PORT = 587
DEFAULT_CACHE_ENTRIES = 500
DEFAULT_CACHE_BYTES = 32 * 1024 * 1024
TRUE_VALUES = frozenset({"1", "true", "yes", "si", "sì"})


def _flag(environ: Mapping[str, str], name: str, default: bool) -> bool:
    raw = environ.get(name)
    return default if raw is None else raw.strip().lower() in TRUE_VALUES


def _int(environ: Mapping[str, str], name: str, default: int) -> int:
    raw = environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} deve essere un intero, non {raw!r}") from None
    if value < 1:
        raise ConfigError(f"{name} deve essere positivo")
    return value


def _site_url(name: str, environ: Mapping[str, str]) -> str:
    """D-62: in produzione obbligatorio, https e senza percorso; mai preso dalla richiesta."""
    raw = (environ.get("SITE_URL") or SITE_DEFAULTS.get(name, "")).strip().rstrip("/")
    parts = urlsplit(raw)
    if not raw or not parts.netloc:
        raise ConfigError(
            "SITE_URL mancante: indirizzo pubblico del sito, es. https://www.esempio.ch"
        )
    if name == "production" and parts.scheme != "https":
        raise ConfigError("SITE_URL deve usare https in produzione")
    if parts.path or parts.query or parts.fragment:
        raise ConfigError("SITE_URL non deve contenere un percorso: solo https://dominio")
    return raw


def _matomo(environ: Mapping[str, str]) -> dict[str, str | None]:
    url = (environ.get("MATOMO_URL") or "").strip().rstrip("/") or None
    site_id = (environ.get("MATOMO_SITE_ID") or "").strip() or None
    if url is not None and (urlsplit(url).scheme != "https" or not urlsplit(url).netloc):
        raise ConfigError("MATOMO_URL deve essere un indirizzo https")
    if site_id is not None and not site_id.isdigit():
        raise ConfigError("MATOMO_SITE_ID deve essere un numero")
    return {"MATOMO_URL": url, "MATOMO_SITE_ID": site_id}


def _mail(name: str, environ: Mapping[str, str]) -> dict[str, Any]:
    security = environ.get("SMTP_SECURITY", "starttls").strip().lower()
    if security not in SMTP_SECURITY_MODES:
        raise ConfigError("SMTP_SECURITY deve essere starttls, ssl oppure none")
    if name == "production" and security == "none":
        raise ConfigError(
            "SMTP_SECURITY=none non è ammesso in produzione: le email viaggerebbero in chiaro"
        )
    return {
        "MAIL_BACKEND": environ.get("MAIL_BACKEND") or MAIL_BACKENDS[name],
        "MAIL_FROM": environ.get("MAIL_FROM") or None,
        "SMTP_HOST": environ.get("SMTP_HOST") or None,
        "SMTP_PORT": _int(environ, "SMTP_PORT", DEFAULT_SMTP_PORT),
        "SMTP_USER": environ.get("SMTP_USER") or None,
        "SMTP_PASSWORD": environ.get("SMTP_PASSWORD") or None,
        "SMTP_SECURITY": security,
        "CONTACT_RECIPIENT": environ.get("CONTACT_RECIPIENT") or None,
    }


def site_config(name: str, environ: Mapping[str, str]) -> dict[str, Any]:
    return {
        "SITE_URL": _site_url(name, environ),
        "SITE_NAME": (environ.get("SITE_NAME") or "").strip() or "Sito",
        # Fuori produzione i motori di ricerca non devono indicizzare (D-62).
        "ROBOTS_ALLOW_INDEXING": _flag(environ, "ROBOTS_ALLOW_INDEXING", name == "production"),
        "PAGE_CACHE_MAX_ENTRIES": _int(environ, "PAGE_CACHE_MAX_ENTRIES", DEFAULT_CACHE_ENTRIES),
        "PAGE_CACHE_MAX_BYTES": _int(environ, "PAGE_CACHE_MAX_BYTES", DEFAULT_CACHE_BYTES),
        **_matomo(environ),
        **_mail(name, environ),
    }
