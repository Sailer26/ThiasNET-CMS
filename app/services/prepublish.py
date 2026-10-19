"""Controllo prima di pubblicare (D-09, D-135).

Bloccanti: gli stessi errori di `publishing.publish` (campi obbligatori, immagini senza testo
alternativo...). Avvisi, che non bloccano: descrizione per i motori di ricerca vuota, pagina
senza blocchi, link interni che non portano a una pagina online o a un media esistente.
Non scrive nulla: nemmeno le programmazioni scadute (le pubblica il cron).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

from flask import current_app
from sqlalchemy import select

from app.extensions import db
from app.models.media import Media
from app.models.page import Page
from app.services import drafts, media_storage, public_pages, publishing
from app.services.blocks import FieldError, join_path
from app.services.public_pages import Outcome
from app.services.theme import Theme, active_theme

MAX_LINKS = 200  # oltre, il controllo smette: è un aiuto, non una scansione completa
MAX_HOPS = 3  # forme da correggere ("/pagina/", "/it/pagina") e vecchi indirizzi
SEO_EMPTY = FieldError(
    "seo/description",
    "seo_empty",
    "Manca la descrizione per i motori di ricerca: Google mostrerà un pezzo di testo a caso.",
)
PAGE_EMPTY = FieldError("zones", "page_empty", "La pagina non ha ancora nessun blocco.")
LINK_BROKEN = "Il link {href} porta a una pagina che non esiste o non è ancora online."


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.hrefs.extend(value for name, value in attrs if name == "href" and value)


def _hrefs(value: str) -> list[str]:
    """Un campo link ("/contatti") o i link di un testo formattato."""
    if "<a" in value:
        parser = _Links()
        parser.feed(value)
        return parser.hrefs
    # Un testo semplice è un link solo se è tutto attaccato ("/ 24 ore" è un titolo).
    looks_like_link = value.startswith(("/", "http")) and not any(ch.isspace() for ch in value)
    return [value] if looks_like_link else []


def _strings(value: Any, path: str) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, join_path(path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, join_path(path, index))


def _site_path(href: str) -> str | None:
    """Percorso del sito da controllare, oppure None (esterno, ancora, mailto...)."""
    site = current_app.config.get("SITE_URL") or ""
    if site and (href == site or href.startswith(f"{site}/")):
        href = href[len(site) :] or "/"
    if not href.startswith("/") or href.startswith("//"):
        return None
    return urlsplit(href).path or "/"


def _media_exists(path: str) -> bool:
    parts = path.split("/")  # "", "media", chiave, file
    if len(parts) != 4 or not media_storage.KEY_RE.fullmatch(parts[2]):
        return False
    query = select(Media.id).where(Media.storage_key == parts[2])
    return db.session.execute(query).first() is not None


def _reachable(path: str, theme: Theme, now: datetime) -> bool:
    """Come il sito: si seguono i redirect (pochi) e conta solo se si arriva a una pagina."""
    for _ in range(MAX_HOPS):
        if path.startswith("/media/"):
            return _media_exists(path)
        if path.split("/", 2)[1] in {"assets", "admin", "api", "static"}:
            return True  # non sono pagine: non si controllano
        resolution = public_pages.resolve(path, theme, now, publish_due=False)
        if resolution.outcome is Outcome.PAGE:
            return True
        if resolution.outcome is Outcome.NOT_FOUND or not resolution.location:
            return False
        path = urlsplit(resolution.location).path or "/"
    return False


def _broken_links(document: dict[str, Any]) -> list[FieldError]:
    theme, now = active_theme(), datetime.now(UTC)
    found: dict[str, FieldError] = {}  # un avviso per campo
    checked = 0
    for path, value in _block_strings(document):
        for href in _hrefs(value):
            checked += 1  # ogni link conta, anche quelli esterni: il lavoro resta limitato
            if checked > MAX_LINKS:
                return list(found.values())
            target = _site_path(href)
            if target is None or path in found:
                continue
            if not _reachable(target, theme, now):
                found[path] = FieldError(path, "link_broken", LINK_BROKEN.format(href=href))
    return list(found.values())


def _block_strings(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    """Testi dei blocchi; una bozza non valida può avere forme strane: si salta ciò che non va."""
    zones = document.get("zones")
    if not isinstance(zones, dict):
        return
    for zone, blocks in zones.items():
        if not isinstance(blocks, list):
            continue
        for index, block in enumerate(blocks):
            if isinstance(block, dict) and isinstance(block.get("data"), dict):
                yield from _strings(block["data"], join_path("zones", zone, index, "data"))


def _warnings(document: dict[str, Any]) -> list[FieldError]:
    warnings: list[FieldError] = []
    seo = document.get("seo") or {}
    if not str(seo.get("description") or "").strip():
        warnings.append(SEO_EMPTY)
    zones = document.get("zones")
    if isinstance(zones, dict) and not any(zones.values()):
        warnings.append(PAGE_EMPTY)
    return warnings + _broken_links(document)


def _source(page: Page) -> Any:
    draft = drafts.load(page.id)
    return draft.data_json if draft is not None else drafts.published_document(page)


def report(page: Page) -> dict[str, list[dict[str, str]]]:
    source = _source(page)
    document, blocking = publishing.problems(source)
    checked = document if document is not None else source
    warnings = _warnings(checked) if isinstance(checked, dict) else []
    return {
        "blocking": [error.as_dict() for error in blocking],
        "warnings": [warning.as_dict() for warning in warnings],
    }
