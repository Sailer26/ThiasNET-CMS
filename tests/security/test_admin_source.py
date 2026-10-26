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
    "Function(": "codice costruito al volo",
    "javascript:": "link che eseguono codice",
    "srcDoc": "HTML inserito come stringa",
    "document.cookie": "il cookie di sessione non si tocca dal pannello",
    "window.open": "nuove finestre solo con link e rel=noopener",
}
# Navigazione verso indirizzi costruiti con dati: niente redirect aperti.
# Assegnazione (non confronto: "href ===" è solo una lettura).
LOCATION_WRITE = re.compile(r"location\.(href\s*=(?!=)|assign\(|replace\()")
STRING_TIMER = re.compile(r"setTimeout\(\s*['\"`]")
BLANK_WITHOUT_REL = re.compile(r"target=\"_blank\"(?![^>]*rel=\"noopener noreferrer\")")
PROTOCOL_RELATIVE = re.compile(r"['\"`]//[a-z0-9]", re.IGNORECASE)
# Un host vero dopo "//": "https://" dentro un messaggio o un modello di testo non conta.
EXTERNAL_URL = re.compile(r"https?://[A-Za-z0-9][^\s'\"`)]*")
ALLOWED_URLS = frozenset({"http://www.w3.org/2000/svg"})  # namespace SVG, non una richiesta
POST_MESSAGE_ANY = re.compile(r"postMessage\([^)]*['\"]\*['\"]")
# Uniche eccezioni, file per file: la lingua del pannello ricordata su quel computer (D-159).
# Mai token o dati del sito: il test qui sotto controlla che si salvi solo quella chiave.
EXEMPT = {"session/LocaleProvider.tsx": frozenset({"localStorage"})}
LOCALE_PROVIDER = SRC / "session" / "LocaleProvider.tsx"


def _sources() -> list[Path]:
    return sorted(
        path
        for path in SRC.rglob("*")
        if path.suffix in {".ts", ".tsx"}
        and ".test." not in path.name
        and "test" not in path.relative_to(SRC).parts[:1]
    )


def test_location_guard_ignores_comparisons() -> None:
    assert LOCATION_WRITE.search('window.location.href = "/x"')
    assert not LOCATION_WRITE.search('frame.location.href === "about:blank"')


def test_panel_sources_exist() -> None:
    assert _sources(), "admin/src senza sorgenti: il guardiano non controllerebbe nulla"


@pytest.mark.parametrize("path", _sources(), ids=lambda p: p.relative_to(SRC).as_posix())
def test_panel_source_is_safe(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    allowed = EXEMPT.get(path.relative_to(SRC).as_posix(), frozenset())
    problems = [
        f"{token}: {why}"
        for token, why in FORBIDDEN.items()
        if token in text and token not in allowed
    ]
    problems += [
        f"indirizzo esterno {url}" for url in EXTERNAL_URL.findall(text) if url not in ALLOWED_URLS
    ]
    if POST_MESSAGE_ANY.search(text):
        problems.append('postMessage verso "*": usare window.location.origin')
    checks = {
        LOCATION_WRITE: "navigazione verso un indirizzo calcolato (usare navigate())",
        STRING_TIMER: "setTimeout con codice in una stringa",
        BLANK_WITHOUT_REL: 'target="_blank" senza rel="noopener noreferrer"',
        PROTOCOL_RELATIVE: "indirizzo esterno senza protocollo (//host)",
    }
    problems += [why for pattern, why in checks.items() if pattern.search(text)]
    assert not problems, problems


def test_locale_provider_stores_only_the_language() -> None:
    """D-159: nel browser resta solo il codice della lingua, sotto una chiave fissa."""
    text = LOCALE_PROVIDER.read_text(encoding="utf-8")
    assert re.findall(r"localStorage\.(\w+)\(", text) == ["getItem", "setItem"]
    assert "localStorage.setItem(LOCALE_STORAGE_KEY, locale)" in text
    assert "localStorage.getItem(LOCALE_STORAGE_KEY)" in text
    assert 'LOCALE_STORAGE_KEY = "thiasnet.panel-locale"' in text
