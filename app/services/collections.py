"""Raccolte del tema (D-147): lo schema dei campi nasce da `theme.json`.

Ogni tipo di campo diventa uno JSON Schema chiuso e si valida con lo stesso motore dei blocchi
(`BlockRegistry`): testo semplice ripulito, testo formattato con l'allowlist nh3, media come id,
url sicuri. Niente HTML libero, niente template: i campi sono solo dati (regola d'oro).

Documento di una voce: `{title, fields: {...}, seo: {...}}` (come la bozza di una pagina).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any

from flask import current_app
from jsonschema import Draft202012Validator

from app.models.media import MediaKind
from app.models.page import TITLE_MAX_LENGTH
from app.services.blocks import BlockRegistry, FieldError, MediaRef, Mode, plain, schema_errors
from app.services.content import DOCUMENT_SCHEMA, OG_IMAGE_KEY, check_size, clean_seo, invalid
from app.services.errors import not_found
from app.services.sanitize import clean_line
from app.services.theme import CollectionSpec, FieldSpec, Theme

REGISTRY_KEY = "thiasnet.collections_registry"
STRING_LIMITS = {"text": 200, "textarea": 2000, "richtext": 20_000, "url": 2048}
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
DATE_TYPES = frozenset({"date", "datetime"})
YEARS = range(1900, 2101)
DATETIME_MAX_LENGTH = 40
OG_PATH = f"seo/{OG_IMAGE_KEY}"

_SHAPE = Draft202012Validator(
    {
        "type": "object",
        "additionalProperties": False,
        "required": ["title", "fields", "seo"],
        "properties": {
            "title": {"type": "string", "maxLength": TITLE_MAX_LENGTH},
            "fields": {"type": "object"},
            "seo": DOCUMENT_SCHEMA["properties"]["seo"],
        },
    }
)


def spec(theme: Theme, key: str) -> CollectionSpec:
    found = theme.collections.get(key)
    if found is None:
        raise not_found("Raccolta non prevista dal tema")
    return found


# --- Schema dei campi ------------------------------------------------------------------


def _field_schema(field: FieldSpec) -> dict[str, Any]:
    base: dict[str, Any] = {"title": field.label}
    kind = field.type
    if kind in STRING_LIMITS:
        base |= {"type": "string", "maxLength": field.max or STRING_LIMITS[kind]}
        if kind == "richtext":
            base["x-richtext"] = True
        elif kind == "textarea":
            base["x-multiline"] = True
        elif kind == "url":
            base["format"] = "safe-url"
    elif kind == "date":
        base |= {"type": "string", "maxLength": 10, "x-date": True}
    elif kind == "datetime":
        base |= {"type": "string", "maxLength": DATETIME_MAX_LENGTH, "x-datetime": True}
    elif kind == "media":
        base |= {"type": "integer", "minimum": 1, "x-media": "image"}
    elif kind == "boolean":
        base["type"] = "boolean"
    else:  # number
        base["type"] = "number"
        if field.max is not None:
            base["maximum"] = field.max
    return base


def collection_schema(collection: CollectionSpec) -> dict[str, Any]:
    return {
        "title": collection.label,
        "type": "object",
        "additionalProperties": False,
        "properties": {name: _field_schema(f) for name, f in collection.fields.items()},
        "required": [name for name, f in collection.fields.items() if f.required],
    }


@dataclass(frozen=True)
class _Cached:
    theme: Theme
    registry: BlockRegistry


def registry(theme: Theme) -> BlockRegistry:
    """Un registro per il tema attivo (come il renderer): si rifà solo se il tema cambia."""
    cached = current_app.extensions.get(REGISTRY_KEY)
    if isinstance(cached, _Cached) and cached.theme is theme:
        return cached.registry
    built = BlockRegistry({key: collection_schema(c) for key, c in theme.collections.items()})
    current_app.extensions[REGISTRY_KEY] = _Cached(theme, built)
    return built


def has_media(theme: Theme, key: str) -> bool:
    collection = theme.collections.get(key)
    return collection is not None and any(f.type == "media" for f in collection.fields.values())


def public_schema(theme: Theme, key: str) -> dict[str, Any]:
    result: dict[str, Any] = plain(registry(theme).schema(key))
    return result


# --- Validazione -------------------------------------------------------------------------


def _parse_date(value: str) -> date | None:
    if not DATE_RE.fullmatch(value):
        return None
    try:
        found = date.fromisoformat(value)
    except ValueError:
        return None
    return found if found.year in YEARS else None


def _parse_datetime(value: str) -> datetime | None:
    try:
        found = datetime.fromisoformat(value)
        if found.tzinfo is None:
            return None
        moment = found.astimezone(UTC)
    except (ValueError, OverflowError):
        return None
    return moment if moment.year in YEARS else None


def _dates(collection: CollectionSpec, fields: dict[str, Any]) -> list[FieldError]:
    """Date come "AAAA-MM-GG"; data e ora con il fuso, salvate in UTC (D-122)."""
    errors: list[FieldError] = []
    for name, field in collection.fields.items():
        value = fields.get(name)
        if field.type not in DATE_TYPES or not isinstance(value, str):
            continue
        path = f"fields/{name}"
        if field.type == "date":
            if _parse_date(value) is None:
                errors.append(FieldError(path, "invalid_date", "Data non valida"))
        else:
            moment = _parse_datetime(value)
            if moment is None:
                errors.append(FieldError(path, "invalid_datetime", "Data e ora non valide"))
            else:
                fields[name] = moment.isoformat()
    return errors


def _without_empty_dates(collection: CollectionSpec, fields: Any) -> Any:
    """Un campo data svuotato nel pannello arriva come "": vale come non compilato."""
    if not isinstance(fields, dict):
        return fields
    dates = {name for name, field in collection.fields.items() if field.type in DATE_TYPES}
    return {k: v for k, v in fields.items() if not (v == "" and k in dates)}


def validate(theme: Theme, key: str, document: Any, mode: Mode) -> dict[str, Any]:
    """Documento pulito di una voce, oppure ServiceError 422 (413 se enorme). Non modifica
    mai quello ricevuto."""
    collection = spec(theme, key)
    check_size(document)
    shape = schema_errors(_SHAPE, document, "")
    if shape:
        raise invalid(shape)
    title = clean_line(document["title"])
    errors: list[FieldError] = []
    if mode is Mode.PUBLISH and not title:
        errors.append(FieldError("title", "required", "Campo obbligatorio"))
    found = registry(theme)
    fields = found.clean(key, _without_empty_dates(collection, document["fields"]))
    errors += found.errors(key, fields, mode, "fields")
    if not errors:
        errors += _dates(collection, fields)
    if errors:
        raise invalid(errors)
    return {"title": title, "fields": fields, "seo": clean_seo(document["seo"])}


def lenient(theme: Theme, key: str, fields: Mapping[str, Any]) -> dict[str, Any]:
    """Campi per il sito: solo quelli che il tema dichiara ancora (D-53, mai un errore)."""
    collection = theme.collections.get(key)
    if collection is None:
        return {}
    return {name: value for name, value in fields.items() if name in collection.fields}


# --- Ordine e media ----------------------------------------------------------------------


def sort_moment(
    theme: Theme, key: str, fields: Mapping[str, Any], published_at: datetime | None
) -> datetime | None:
    """L'ordine dell'elenco: la prima data obbligatoria della raccolta, se c'è."""
    collection = theme.collections.get(key)
    for name, field in collection.fields.items() if collection else ():
        value = fields.get(name)
        if not field.required or field.type not in DATE_TYPES or not isinstance(value, str):
            continue
        if field.type == "date":
            day = _parse_date(value)
            if day is not None:
                return datetime.combine(day, time(), UTC)
        else:
            moment = _parse_datetime(value)
            if moment is not None:
                return moment
    return published_at


def media_refs(theme: Theme, key: str, document: Any) -> list[MediaRef]:
    """I media di una voce: i campi immagine e l'immagine per i social."""
    if not isinstance(document, Mapping) or key not in theme.collections:
        return []
    refs = list(registry(theme).media_refs(key, document.get("fields"), "fields"))
    seo = document.get("seo")
    og = seo.get(OG_IMAGE_KEY) if isinstance(seo, Mapping) else None
    if isinstance(og, int) and not isinstance(og, bool):
        refs.append(MediaRef(og, MediaKind.IMAGE, OG_PATH))
    return refs
