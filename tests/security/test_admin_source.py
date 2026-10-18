"""Guardiano del sorgente del pannello React (D-98): gira anche senza Node.

Il pannello non inserisce mai HTML come stringa, non esegue codice costruito al volo,
non salva token nel browser, non parla con siti esterni e non tiene viva la sessione con
dei timer (D-90). I test (`*.test.ts(x)`, `src/test/`) sono esclusi.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "admin" / "src"
FORBIDDEN = {
    "dangerouslySetInnerHTML": "HTML inserito come stringa",
    "innerHTML": "HTML inserito come stringa",
    "outerHTML": "HTML inserito come stringa",
    "insertAdjacentHTML": "HTML inserito come stringa",
    "document.write": "HTML inserito come stringa",
    "eval(": "codice costruito al volo",
    "new Function": "codice costruito al volo",
    "localStorage": "dati nel browser (D-90: il token CSRF vive solo in memoria)",
    "sessionStorage": "dati nel browser (D-90: il token CSRF vive solo in memoria)",
    "setInterval": "timer che terrebbero viva la sessione (D-90)",
}
EXTERNAL_URL = re.compile(r"https?://[^\s'\"`)]+")
ALLOWED_URLS = frozenset({"http://www.w3.org/2000/svg"})  # namespace SVG, non una richiesta
POST_MESSAGE_ANY = re.compile(r"postMessage\([^)]*['\"]\*['\"]")


def _sources() -> list[Path]:
    return sorted(
        path
        for path in SRC.rglob("*")
        if path.suffix in {".ts", ".tsx"}
        and ".test." not in path.name
        and "test" not in path.relative_to(SRC).parts[:1]
    )


def test_panel_sources_exist() -> None:
    assert _sources(), "admin/src senza sorgenti: il guardiano non controllerebbe nulla"


@pytest.mark.parametrize("path", _sources(), ids=lambda p: p.relative_to(SRC).as_posix())
def test_panel_source_is_safe(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    problems = [f"{token}: {why}" for token, why in FORBIDDEN.items() if token in text]
    problems += [
        f"indirizzo esterno {url}" for url in EXTERNAL_URL.findall(text) if url not in ALLOWED_URLS
    ]
    if POST_MESSAGE_ANY.search(text):
        problems.append('postMessage verso "*": usare window.location.origin')
    assert not problems, problems
