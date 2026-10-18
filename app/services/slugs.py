"""Slug delle pagine (D-45): solo minuscole, cifre e trattini, generati dal titolo."""

from __future__ import annotations

import re
import unicodedata

from app.models.page import SLUG_MAX_LENGTH
from app.services.errors import ServiceError

SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
LOCALE_CODES = frozenset({"it", "de", "rm", "en"})
# Primi segmenti usati dal sito o dal pannello: una pagina di primo livello non li può avere.
RESERVED_SEGMENTS = frozenset(
    {"api", "admin", "_preview", "static", "media", "assets", "sitemap.xml", "robots.txt"}
    | LOCALE_CODES
)
# Le dieresi tedesche diventano due lettere (Über → ueber), come si scrive senza tastiera.
TRANSLITERATION = str.maketrans(
    {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss", "ẞ": "SS"}
)
_NOT_ALLOWED = re.compile(r"[^a-z0-9]+")

__all__ = ["SLUG_MAX_LENGTH", "is_reserved", "slugify", "validate_slug"]


def slugify(title: str) -> str:
    """Slug dal titolo, tagliato a fine parola entro SLUG_MAX_LENGTH. Può essere vuoto."""
    text = unicodedata.normalize("NFKD", title.translate(TRANSLITERATION))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    slug = _NOT_ALLOWED.sub("-", text).strip("-")
    if len(slug) <= SLUG_MAX_LENGTH:
        return slug
    cut = slug[:SLUG_MAX_LENGTH]
    if slug[SLUG_MAX_LENGTH] != "-" and "-" in cut:
        cut = cut.rsplit("-", 1)[0]
    return cut.strip("-")


def validate_slug(slug: str) -> None:
    if len(slug) > SLUG_MAX_LENGTH or not SLUG_RE.fullmatch(slug):
        raise ServiceError(
            "invalid_slug",
            f"Indirizzo non valido: usa lettere minuscole, numeri e trattini "
            f"(massimo {SLUG_MAX_LENGTH} caratteri)",
            422,
        )


def is_reserved(slug: str) -> bool:
    """Vale solo per il primo livello: "/servizi/de" va bene, "/de" no."""
    return slug in RESERVED_SEGMENTS
