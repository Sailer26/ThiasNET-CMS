"""Pulizia del testo dei blocchi (D-49).

- Testo semplice: normalizzato e mai trattato come HTML (lo escapa il tema).
- Rich text: solo l'allowlist (CLAUDE.md + `br`, D-49), passata da nh3; link solo sicuri.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

import nh3

MAX_URL_LENGTH = 2048
RICH_TAGS = frozenset(
    {"p", "h2", "h3", "h4", "strong", "em", "a", "ul", "ol", "li", "blockquote", "br"}
)
RICH_ATTRIBUTES = {"a": {"href"}}
LINK_REL = "noopener noreferrer"
URL_SCHEMES = frozenset({"http", "https", "mailto", "tel"})
# Tag eliminati insieme al loro contenuto (gli altri tag non ammessi lasciano il solo testo).
DROPPED_WITH_CONTENT = frozenset(
    {
        "script",
        "style",
        "noscript",
        "template",
        "iframe",
        "object",
        "embed",
        "svg",
        "math",
        "textarea",
        "title",
        "xmp",
        "noembed",
        "noframes",
    }
)
TEL_RE = re.compile(r"\+?[0-9().-]{3,30}")
ANCHOR_RE = re.compile(r"#[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}")
# Caratteri invisibili che servono solo a ingannare chi legge (testo bidirezionale
# rovesciato, separatori invisibili, BOM). ZWJ e ZWNJ restano: servono alle emoji.
INVISIBLE_FORMAT = frozenset(
    chr(code)
    for code in (
        0x200B,
        0x200E,
        0x200F,
        0x2060,
        0x2061,
        0x2062,
        0x2063,
        0x2064,
        0xFEFF,
        *range(0x202A, 0x202F),
        *range(0x2066, 0x206A),
    )
)
DROPPED_CATEGORIES = frozenset({"Cc", "Cs", "Co"})
AS_SPACE = frozenset({chr(9), chr(0x2028), chr(0x2029)})  # tab, separatori di riga e paragrafo


def _keep(ch: str) -> bool:
    if ch == "\n":
        return True
    return ch not in INVISIBLE_FORMAT and unicodedata.category(ch) not in DROPPED_CATEGORIES


def _strip_controls(value: str) -> str:
    """NFC, a capo uniformi, tab come spazio, niente caratteri di controllo o invisibili."""
    value = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    return "".join(" " if ch in AS_SPACE else ch for ch in value if ch in AS_SPACE or _keep(ch))


def clean_plain(value: str) -> str:
    return _strip_controls(value).strip()


def clean_line(value: str) -> str:
    """Per i campi su una riga (titoli): niente a capo, spazi consecutivi ridotti a uno."""
    return " ".join(clean_plain(value).split())


def normalize_url(value: str) -> str:
    """I numeri di telefono si scrivono con gli spazi: nel link li togliamo."""
    value = value.strip()
    if value[:4].lower() == "tel:":
        return "tel:" + "".join(value[4:].split())
    return value


def is_safe_url(value: str) -> bool:
    """http(s) con host, mailto, tel, ancora (#...) o percorso del sito ("/", mai "//")."""
    if not value or len(value) > MAX_URL_LENGTH or "\\" in value:
        return False
    if any(ch.isspace() or unicodedata.category(ch).startswith("C") for ch in value):
        return False
    if value.startswith("/"):
        return not value.startswith("//")
    if value.startswith("#"):
        return ANCHOR_RE.fullmatch(value) is not None
    scheme, sep, rest = value.partition(":")
    scheme = scheme.lower()
    if not sep or scheme not in URL_SCHEMES or not rest:
        return False
    if scheme in {"http", "https"}:
        try:
            return bool(urlsplit(value).hostname)
        except ValueError:
            return False
    if scheme == "tel":
        return TEL_RE.fullmatch(rest) is not None
    return True


def _filter_attribute(tag: str, attribute: str, value: str) -> str | None:
    if tag == "a" and attribute == "href":
        url = normalize_url(value)
        return url if is_safe_url(url) else None
    return value


def clean_rich(html: str) -> str:
    """HTML ripulito con allowlist. Idempotente: ripulire due volte dà lo stesso risultato.
    Chi chiama limita prima la lunghezza: nh3 è lento su annidamenti enormi."""
    cleaned: str = nh3.clean(
        _strip_controls(html),
        tags=set(RICH_TAGS),
        clean_content_tags=set(DROPPED_WITH_CONTENT),
        attributes={tag: set(attrs) for tag, attrs in RICH_ATTRIBUTES.items()},
        attribute_filter=_filter_attribute,
        strip_comments=True,
        link_rel=LINK_REL,
        url_schemes=set(URL_SCHEMES),
    )
    return cleaned.strip()
