"""Build del pannello React (D-87, D-88): dove sta, quali file si possono servire, CSP.

Solo lettura: il pannello è codice di ThiasNET compilato al deploy, mai caricato dal pannello.
"""

from __future__ import annotations

from pathlib import Path

from flask import current_app

ASSET_SUFFIXES = frozenset({".js", ".css", ".woff2", ".png"})
MISSING_BUILD = (
    "Pannello non ancora compilato: esegui `python scripts/tasks.py admin-build` "
    "e ricarica la pagina."
)
PANEL_CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self'",
        "font-src 'self'",
        "connect-src 'self'",
        "frame-src 'self'",  # anteprima live (D-55)
        "frame-ancestors 'none'",
        "form-action 'self'",
        "base-uri 'none'",
        "object-src 'none'",
    ]
)
PANEL_HEADERS = {
    "Content-Security-Policy": PANEL_CSP,
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
}


def dist_dir() -> Path:
    return Path(current_app.config["ADMIN_DIST_DIR"])


def index_file() -> Path | None:
    path = dist_dir() / "index.html"
    return path if path.is_file() else None


def asset_path(filename: str) -> Path | None:
    """Solo file esistenti in `assets/` della build, con un'estensione ammessa."""
    if "\\" in filename or Path(filename).suffix.lower() not in ASSET_SUFFIXES:
        return None
    root = (dist_dir() / "assets").resolve()
    candidate = (root / filename).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    return candidate
