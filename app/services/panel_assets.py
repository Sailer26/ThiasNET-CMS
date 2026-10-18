"""Build del pannello React (D-87, D-88): dove sta, quali file si possono servire, CSP.

Solo lettura: il pannello è codice di ThiasNET compilato al deploy, mai caricato dal pannello.
"""

from __future__ import annotations

from pathlib import Path

from flask import current_app

# Tipi fissi: su Windows `mimetypes` legge il registro, che a volte dice text/plain per .js
# (con nosniff il browser rifiuterebbe il pannello).
ASSET_TYPES = {
    ".js": "text/javascript",
    ".css": "text/css",
    ".woff2": "font/woff2",
    ".png": "image/png",
}
MISSING_BUILD = (
    "Pannello non ancora compilato: esegui `python scripts/tasks.py admin-build` "
    "e ricarica la pagina."
)
PANEL_CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' blob:",  # anteprima dei file scelti prima del caricamento (D-118)
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


NUL = chr(0)  # carattere nullo: il filesystem lo rifiuta


def asset_type(path: Path) -> str:
    return ASSET_TYPES[path.suffix.lower()]


def asset_path(filename: str) -> Path | None:
    """Solo file esistenti in `assets/` della build, con un'estensione ammessa."""
    if "\\" in filename or NUL in filename or Path(filename).suffix.lower() not in ASSET_TYPES:
        return None
    try:
        root = (dist_dir() / "assets").resolve()
        candidate = (root / filename).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            return None
    except (OSError, ValueError):  # nomi che il sistema non accetta: semplicemente non esistono
        return None
    return candidate
