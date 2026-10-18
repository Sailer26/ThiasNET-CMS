"""Documento di una pagina (bozza, revisione, istantanea programmata) e regole del tema.

Forma: `{title, layout, seo: {...}, zones: {zona: [{uid, type, variant, data}]}}` (D-38).
`validate_document` pulisce e valida in modalità "bozza" o "pubblica" (D-46) e restituisce
un documento nuovo: quello ricevuto non viene mai modificato.
"""

from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator

from app.core_types import BLOCK_TYPES
from app.models.page import NAME_MAX_LENGTH, TITLE_MAX_LENGTH
from app.services.blocks import FieldError, Mode, get_registry, join_path, schema_errors
from app.services.errors import ServiceError
from app.services.sanitize import clean_line
from app.services.theme import Theme

MAX_BLOCKS = 200
MAX_DOCUMENT_BYTES = 512 * 1024
MAX_ZONES = 32
UID_PATTERN = "^[0-9a-f]{32}$"
SEO_FIELDS = ("title", "description")

_BLOCK_SHAPE: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["uid", "type", "data"],
    "properties": {
        # minLength/maxLength: in Python "$" accetta anche un a capo finale.
        "uid": {"type": "string", "minLength": 32, "maxLength": 32, "pattern": UID_PATTERN},
        "type": {"type": "string", "enum": sorted(BLOCK_TYPES)},
        "variant": {"type": ["string", "null"], "maxLength": NAME_MAX_LENGTH},
        "data": {"type": "object"},
    },
}
DOCUMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "layout", "seo", "zones"],
    "properties": {
        "title": {"type": "string", "maxLength": TITLE_MAX_LENGTH},
        "layout": {"type": "string", "maxLength": NAME_MAX_LENGTH},
        "seo": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "title": {"type": "string", "maxLength": 70},
                "description": {"type": "string", "maxLength": 160},
                "og_image_media_id": {"type": "integer", "minimum": 1},
                "noindex": {"type": "boolean"},
            },
        },
        "zones": {
            "type": "object",
            "maxProperties": MAX_ZONES,
            "propertyNames": {"maxLength": NAME_MAX_LENGTH},
            # Il totale dei blocchi (MAX_BLOCKS) si controlla su tutte le zone insieme.
            "additionalProperties": {"type": "array", "items": _BLOCK_SHAPE},
        },
    },
}
_SHAPE = Draft202012Validator(DOCUMENT_SCHEMA)


def invalid(errors: list[FieldError]) -> ServiceError:
    return ServiceError(
        "invalid_content",
        "Alcuni campi non sono validi: controlla quelli evidenziati",
        422,
        details=[e.as_dict() for e in sorted(set(errors), key=lambda e: (e.path, e.code))],
    )


def empty_document(theme: Theme, title: str, layout: str) -> dict[str, Any]:
    return {
        "title": title,
        "layout": layout,
        "seo": {},
        "zones": {z: [] for z in theme.zones(layout)},
    }


def _check_size(document: Any) -> None:
    """Dimensione massima, niente NaN/Infinity (JSON non valido per il pannello) né
    annidamenti senza fine."""
    try:
        encoded = json.dumps(document, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (ValueError, RecursionError):
        raise invalid(
            [FieldError("", "invalid_json", "Contenuto non valido: numeri o struttura non ammessi")]
        ) from None
    size = len(encoded.encode("utf-8"))
    if size > MAX_DOCUMENT_BYTES:
        raise ServiceError(
            "content_too_large",
            "La pagina è troppo grande: dividi il contenuto in più pagine",
            413,
        )


def _clean_seo(seo: dict[str, Any]) -> dict[str, Any]:
    cleaned = {k: clean_line(v) if k in SEO_FIELDS else v for k, v in seo.items()}
    return {k: v for k, v in cleaned.items() if v != ""}


def _variant(
    theme: Theme, block_type: str, variant: str | None, path: str, errors: list[FieldError]
) -> str | None:
    """D-03: variante assente → default del tema; non dichiarata → errore."""
    variants = theme.variants_for(block_type)
    if variants is None:
        if variant is not None:
            errors.append(
                FieldError(f"{path}/variant", "variant_not_supported", "Blocco senza varianti")
            )
        return None
    if variant is None:
        return variants.default
    if variant not in variants.options:
        errors.append(FieldError(f"{path}/variant", "unknown_variant", "Variante non disponibile"))
    return variant


def _block(
    theme: Theme, block: dict[str, Any], path: str, mode: Mode, errors: list[FieldError]
) -> dict[str, Any]:
    registry = get_registry()
    data = registry.clean(block["type"], block["data"])
    errors += registry.errors(block["type"], data, mode, prefix=f"{path}/data")
    return {
        "uid": block["uid"],
        "type": block["type"],
        "variant": _variant(theme, block["type"], block.get("variant"), path, errors),
        "data": data,
    }


def _zone(
    theme: Theme,
    layout: str,
    zone: str,
    blocks: list[dict[str, Any]],
    seen: set[str],
    mode: Mode,
    errors: list[FieldError],
) -> list[dict[str, Any]]:
    where = join_path("zones", zone)
    if zone not in theme.layouts[layout].zones:
        errors.append(FieldError(where, "unknown_zone", "Zona non prevista da questo layout"))
        return []
    allowed, limit = theme.allowed_blocks(layout, zone), theme.zone_max(layout, zone)
    if limit is not None and len(blocks) > limit:
        errors.append(FieldError(where, "zone_full", f"Al massimo {limit} blocchi in questa zona"))
    result = []
    for index, block in enumerate(blocks):
        path = f"{where}/{index}"
        if block["uid"] in seen:
            errors.append(FieldError(f"{path}/uid", "duplicate_uid", "Blocco duplicato"))
        seen.add(block["uid"])
        if block["type"] not in allowed:
            errors.append(
                FieldError(f"{path}/type", "block_not_allowed", "Blocco non ammesso in questa zona")
            )
        result.append(_block(theme, block, path, mode, errors))
    return result


def validate_document(theme: Theme, document: Any, mode: Mode) -> dict[str, Any]:
    """Documento pulito e valido per `theme`, oppure ServiceError 422 (o 413 se enorme)."""
    _check_size(document)
    shape = schema_errors(_SHAPE, document, "")
    if shape:
        raise invalid(shape)
    layout = document["layout"]
    if layout not in theme.layouts:
        raise invalid([FieldError("layout", "unknown_layout", "Layout non disponibile")])
    if sum(len(blocks) for blocks in document["zones"].values()) > MAX_BLOCKS:
        raise invalid(
            [FieldError("zones", "too_many_blocks", f"Al massimo {MAX_BLOCKS} blocchi per pagina")]
        )

    errors: list[FieldError] = []
    title = clean_line(document["title"])
    if mode is Mode.PUBLISH and not title:
        errors.append(FieldError("title", "required", "Campo obbligatorio"))
    seen: set[str] = set()
    zones = {
        zone: _zone(theme, layout, zone, blocks, seen, mode, errors)
        for zone, blocks in document["zones"].items()
    }
    if errors:
        raise invalid(errors)
    return {
        "title": title,
        "layout": layout,
        "seo": _clean_seo(document["seo"]),
        "zones": {zone: zones.get(zone, []) for zone in theme.zones(layout)},
    }
