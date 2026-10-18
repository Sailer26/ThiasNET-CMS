"""Dati passati ai template: solo strutture congelate preparate dal CMS (D-52).

`normalize_document` rimette in riga un documento salvato con un tema precedente (D-53):
layout di ripiego, zone e blocchi non più ammessi omessi, varianti sconosciute → default.
Non solleva mai eccezioni: al massimo scrive un avviso nel log.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from app.core_types import BLOCK_TYPES
from app.services.theme import Theme

log = logging.getLogger("thiasnet.render")
FALLBACK_LAYOUT = "page"
EMPTY: Mapping[str, Any] = MappingProxyType({})


class RenderMode(StrEnum):
    PUBLIC = "public"
    PREVIEW = "preview"


@dataclass(frozen=True)
class BlockView:
    id: str  # uid stabile (D-39): finisce in data-block-id
    type: str
    variant: str | None
    data: Mapping[str, Any]
    zone: str


@dataclass(frozen=True)
class PageView:
    id: int | None
    locale: str
    title: str
    layout: str
    path: str  # indirizzo pubblico, es. "/de/ueber-uns"
    seo: Mapping[str, Any]
    zones: Mapping[str, tuple[BlockView, ...]]
    is_home: bool

    @property
    def noindex(self) -> bool:
        return bool(self.seo.get("noindex"))


@dataclass(frozen=True)
class Link:
    title: str
    url: str
    current: bool = False


@dataclass(frozen=True)
class SiteInfo:
    name: str
    base_url: str  # SITE_URL, senza "/" finale: canonical e sitemap (D-62)
    locale: str  # lingua principale del sito
    year: int


@dataclass(frozen=True)
class Analytics:
    url: str
    site_id: str


@dataclass(frozen=True)
class ContactFormView:
    """Stato del modulo contatti di un blocco: token fresco, valori ed errori (D-61)."""

    action: str
    token: str
    values: Mapping[str, str] = EMPTY
    errors: Mapping[str, str] = EMPTY
    sent: bool = False
    disabled: bool = False


@dataclass(frozen=True)
class VariantView:
    width: int
    height: int
    url: str


@dataclass(frozen=True)
class MediaView:
    """Un media della libreria come lo vede il tema (D-81)."""

    id: int
    kind: str  # "image" | "document"
    alt: str
    width: int | None
    height: int | None
    url: str
    name: str
    ext: str
    size_bytes: int
    focal_x: int
    focal_y: int
    sizes: Mapping[str, tuple[VariantView, ...]] = EMPTY


@dataclass(frozen=True)
class PageContext:
    page: PageView
    site: SiteInfo
    mode: RenderMode = RenderMode.PUBLIC
    menu: tuple[Link, ...] = ()
    breadcrumbs: tuple[Link, ...] = ()
    settings: Mapping[str, Any] = EMPTY
    css_version: str = ""
    analytics: Analytics | None = None
    forms: Mapping[str, ContactFormView] = field(default_factory=lambda: EMPTY)
    media: Mapping[int, MediaView] = field(default_factory=lambda: MappingProxyType({}))
    og_image: MediaView | None = None


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(v) for v in value)
    return value


def _layout(theme: Theme, layout: Any, page_id: int | None) -> str:
    if isinstance(layout, str) and layout in theme.layouts:
        return layout
    fallback = FALLBACK_LAYOUT if FALLBACK_LAYOUT in theme.layouts else next(iter(theme.layouts))
    log.warning("pagina %s: layout %r non esiste più, uso %r", page_id, layout, fallback)
    return fallback


def _variant(theme: Theme, block_type: str, variant: Any) -> str | None:
    variants = theme.variants_for(block_type)
    if variants is None:
        return None
    return variant if isinstance(variant, str) and variant in variants.options else variants.default


def _block(theme: Theme, layout: str, zone: str, raw: Any, page_id: int | None) -> BlockView | None:
    if not isinstance(raw, Mapping):
        return None
    block_type, uid = raw.get("type"), raw.get("uid")
    allowed = theme.allowed_blocks(layout, zone)
    known = isinstance(block_type, str) and block_type in BLOCK_TYPES
    if not known or block_type not in allowed or not isinstance(uid, str):
        log.warning(
            "pagina %s: blocco %r non ammesso in %s/%s, omesso", page_id, block_type, layout, zone
        )
        return None
    data = raw.get("data")
    return BlockView(
        id=uid,
        type=str(block_type),
        variant=_variant(theme, str(block_type), raw.get("variant")),
        data=_freeze(data) if isinstance(data, Mapping) else EMPTY,
        zone=zone,
    )


def normalize_document(
    theme: Theme,
    document: Any,
    *,
    page_id: int | None,
    locale: str,
    path: str,
    is_home: bool,
) -> PageView:
    if not isinstance(document, Mapping):
        log.warning("pagina %s: documento non leggibile, mostrata vuota", page_id)
        document = {}
    layout = _layout(theme, document.get("layout"), page_id)
    stored = document.get("zones")
    stored = stored if isinstance(stored, Mapping) else {}
    zones: dict[str, tuple[BlockView, ...]] = {}
    for zone in theme.zones(layout):
        raw_blocks = stored.get(zone)
        if not isinstance(raw_blocks, list | tuple):
            raw_blocks = ()
        views = (_block(theme, layout, zone, raw, page_id) for raw in raw_blocks)
        zones[zone] = tuple(view for view in views if view is not None)
    for zone in set(stored) - set(zones):
        log.warning("pagina %s: zona %r non esiste nel layout %r, omessa", page_id, zone, layout)
    seo = document.get("seo")
    return PageView(
        id=page_id,
        locale=locale,
        title=str(document.get("title") or ""),
        layout=layout,
        path=path,
        seo=_freeze(seo) if isinstance(seo, Mapping) else EMPTY,
        zones=MappingProxyType(zones),
        is_home=is_home,
    )
