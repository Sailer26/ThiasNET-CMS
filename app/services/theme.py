"""Lettura e validazione del tema attivo.

Regola d'oro: questo modulo legge il tema e non lo scrive mai. Non aggiungere metodi di
scrittura: il tema cambia solo via git + deploy (CLAUDE.md, TEMPLATE-CONTRACT.md).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from jsonschema import Draft202012Validator

from app.core_types import BLOCK_TYPES, WIDGET_TYPES

THEME_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
# Parole intere (separate da "_"): evita falsi positivi come site_description o postcode.
# Vale solo per i campi a testo libero (un select "header_style" ha opzioni chiuse ed è sicuro).
# È una difesa in più: la protezione vera è l'allowlist dei tipi nello schema.
FREE_TEXT_SETTING_TYPES = frozenset({"text", "textarea", "url"})
SUSPICIOUS_SETTING_KEY_RE = re.compile(
    r"(^|_)(css|js|javascript|script|html|style|stylesheet|head|raw|markup|snippet|embed|"
    r"iframe|template|jinja)(_|$)",
    re.IGNORECASE,
)
MANIFEST_NAME = "theme.json"
_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "theme.schema.json"
_SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
Draft202012Validator.check_schema(_SCHEMA)  # uno schema rotto deve fallire subito e in chiaro
_VALIDATOR = Draft202012Validator(_SCHEMA)


class ThemeValidationError(ValueError):
    """Il tema non rispetta il contratto: l'app non deve partire."""


@dataclass(frozen=True)
class Zone:
    name: str
    label: str
    blocks: tuple[str, ...]
    max: int | None


@dataclass(frozen=True)
class Layout:
    name: str
    label: str
    zones: Mapping[str, Zone]


@dataclass(frozen=True)
class WidgetArea:
    name: str
    label: str
    widgets: tuple[str, ...]


@dataclass(frozen=True)
class VariantOption:
    key: str
    label: str
    thumbnail: str


@dataclass(frozen=True)
class VariantSet:
    default: str
    options: Mapping[str, VariantOption]


@dataclass(frozen=True)
class SettingSpec:
    key: str
    type: str
    label: str
    default: str | bool | None
    max: int | None
    options: tuple[str, ...]
    palette: tuple[str, ...]


@dataclass(frozen=True)
class Theme:
    name: str
    version: str
    author: str
    directory: Path
    locales: tuple[str, ...]
    layouts: Mapping[str, Layout]
    widget_areas: Mapping[str, WidgetArea]
    menus: Mapping[str, Any]
    collections: Mapping[str, Any]
    image_sizes: Mapping[str, Any]
    block_variants: Mapping[str, VariantSet]
    settings: Mapping[str, SettingSpec]

    def zones(self, layout: str) -> tuple[str, ...]:
        return tuple(self.layouts[layout].zones)

    def allowed_blocks(self, layout: str, zone: str) -> tuple[str, ...]:
        return self.layouts[layout].zones[zone].blocks

    def zone_max(self, layout: str, zone: str) -> int | None:
        return self.layouts[layout].zones[zone].max

    def variants_for(self, block_type: str) -> VariantSet | None:
        return self.block_variants.get(block_type)

    def is_valid_variant(self, block_type: str, variant: str | None) -> bool:
        variants = self.variants_for(block_type)
        if variants is None:
            return variant is None
        return variant is not None and variant in variants.options

    def setting(self, key: str) -> SettingSpec:
        return self.settings[key]


def load_theme(themes_dir: Path, name: str) -> Theme:
    """Carica e valida `themes_dir/<name>/theme.json`. Solleva ThemeValidationError."""
    theme_dir = _resolve_theme_dir(themes_dir, name)
    data = _read_manifest(theme_dir, name)
    errors = [_format_schema_error(e) for e in _VALIDATOR.iter_errors(data)]
    if not errors:
        errors = _contract_errors(data, theme_dir, name)
    if errors:
        details = "\n".join(f"  - {e}" for e in sorted(errors))
        raise ThemeValidationError(f"Tema '{name}' non valido:\n{details}")
    return _build_theme(data, theme_dir)


def _resolve_theme_dir(themes_dir: Path, name: str) -> Path:
    if not THEME_NAME_RE.fullmatch(name):
        raise ThemeValidationError(f"Il nome del tema non è valido: {name!r}")
    root = themes_dir.resolve()
    theme_dir = (root / name).resolve()
    if not theme_dir.is_relative_to(root):
        raise ThemeValidationError(f"Il nome del tema esce dalla cartella dei temi: {name!r}")
    return theme_dir


def _read_manifest(theme_dir: Path, name: str) -> Any:
    manifest = theme_dir / MANIFEST_NAME
    if not manifest.is_file():
        raise ThemeValidationError(f"Tema '{name}': {MANIFEST_NAME} non trovato in {theme_dir}")
    try:
        return json.loads(
            manifest.read_bytes(),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise ThemeValidationError(
            f"Tema '{name}': {MANIFEST_NAME} non è JSON valido ({exc})"
        ) from exc


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Con chiavi duplicate json vince l'ultima e il resto sparisce in silenzio: rifiutiamo."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"chiave duplicata {key!r}")
        result[key] = value
    return result


def _reject_constant(constant: str) -> Any:
    raise ValueError(f"valore {constant} non ammesso")


def _format_schema_error(error: Any) -> str:
    location = "/".join(str(part) for part in error.absolute_path) or "(radice)"
    return f"{location}: {error.message}"


def _contract_errors(data: Mapping[str, Any], theme_dir: Path, name: str) -> list[str]:
    """Controlli che lo schema JSON non può esprimere (riferimenti incrociati e file)."""
    errors: list[str] = []
    if data["name"] != name:
        errors.append(f"name: {data['name']!r} deve coincidere con la cartella {name!r}")
    errors += _layout_errors(data.get("layouts", {}))
    errors += _widget_area_errors(data.get("widget_areas", {}))
    errors += _variant_errors(data.get("block_variants", {}), theme_dir)
    errors += _setting_errors(data.get("settings", {}))
    return errors


def _layout_errors(layouts: Mapping[str, Any]) -> list[str]:
    return [
        f"layouts/{layout}/zones/{zone}: blocco sconosciuto {block!r}"
        for layout, spec in layouts.items()
        for zone, zone_spec in spec["zones"].items()
        for block in zone_spec["blocks"]
        if block not in BLOCK_TYPES
    ]


def _widget_area_errors(areas: Mapping[str, Any]) -> list[str]:
    return [
        f"widget_areas/{area}: widget sconosciuto {widget!r}"
        for area, spec in areas.items()
        for widget in spec["widgets"]
        if widget not in WIDGET_TYPES
    ]


def _variant_errors(block_variants: Mapping[str, Any], theme_dir: Path) -> list[str]:
    errors: list[str] = []
    assets_dir = theme_dir / "assets"
    for block, spec in block_variants.items():
        where = f"block_variants/{block}"
        if block not in BLOCK_TYPES:
            errors.append(f"{where}: blocco sconosciuto {block!r}")
        if spec["default"] not in spec["options"]:
            errors.append(
                f"{where}: la variante di default {spec['default']!r} non è tra le opzioni"
            )
        for key, option in spec["options"].items():
            problem = _thumbnail_problem(assets_dir, option["thumbnail"])
            if problem:
                errors.append(f"{where}/options/{key}/thumbnail: {problem}")
    return errors


def _thumbnail_problem(assets_dir: Path, thumbnail: str) -> str | None:
    """D-18: la miniatura deve esistere, non essere vuota e stare dentro assets/."""
    path = (assets_dir / thumbnail).resolve()
    if not path.is_relative_to(assets_dir.resolve()):
        return f"assets/{thumbnail} punta fuori dalla cartella del tema"
    if not path.is_file():
        return f"file mancante assets/{thumbnail}"
    if path.stat().st_size == 0:
        return f"file vuoto assets/{thumbnail}"
    return None


def _setting_errors(settings: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for key, spec in settings.items():
        where = f"settings/{key}"
        if spec["type"] in FREE_TEXT_SETTING_TYPES and SUSPICIOUS_SETTING_KEY_RE.search(key):
            errors.append(f"{where}: nome vietato (niente CSS/JS/HTML/codice nelle impostazioni)")
        default = spec.get("default")
        if spec["type"] == "select" and default is not None and default not in spec["options"]:
            errors.append(f"{where}: il default {default!r} non è tra le opzioni")
        palette = {color.upper() for color in spec.get("palette", ())}
        if spec["type"] == "color" and palette and default and default.upper() not in palette:
            errors.append(f"{where}: il default {default!r} non è nella palette")
    return errors


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


def _build_theme(data: Mapping[str, Any], theme_dir: Path) -> Theme:
    return Theme(
        name=data["name"],
        version=data["version"],
        author=data.get("author", ""),
        directory=theme_dir,
        locales=tuple(data["locales"]),
        layouts=MappingProxyType(
            {name: _build_layout(name, spec) for name, spec in data["layouts"].items()}
        ),
        widget_areas=MappingProxyType(
            {
                name: WidgetArea(name=name, label=spec["label"], widgets=tuple(spec["widgets"]))
                for name, spec in data.get("widget_areas", {}).items()
            }
        ),
        menus=_freeze(data.get("menus", {})),
        collections=_freeze(data.get("collections", {})),
        image_sizes=_freeze(data.get("image_sizes", {})),
        block_variants=MappingProxyType(
            {block: _build_variants(spec) for block, spec in data.get("block_variants", {}).items()}
        ),
        settings=MappingProxyType(
            {key: _build_setting(key, spec) for key, spec in data.get("settings", {}).items()}
        ),
    )


def _build_layout(name: str, spec: Mapping[str, Any]) -> Layout:
    zones = {
        zone: Zone(
            name=zone,
            label=zone_spec.get("label", zone),
            blocks=tuple(zone_spec["blocks"]),
            max=zone_spec.get("max"),
        )
        for zone, zone_spec in spec["zones"].items()
    }
    return Layout(name=name, label=spec["label"], zones=MappingProxyType(zones))


def _build_variants(spec: Mapping[str, Any]) -> VariantSet:
    options = {
        key: VariantOption(key=key, label=option["label"], thumbnail=option["thumbnail"])
        for key, option in spec["options"].items()
    }
    return VariantSet(default=spec["default"], options=MappingProxyType(options))


def _build_setting(key: str, spec: Mapping[str, Any]) -> SettingSpec:
    default = spec.get("default")
    if spec["type"] == "color" and isinstance(default, str):
        default = default.upper()  # colori sempre in maiuscolo: confronti senza sorprese
    return SettingSpec(
        key=key,
        type=spec["type"],
        label=spec["label"],
        default=default,
        max=spec.get("max"),
        options=tuple(spec.get("options", ())),
        palette=tuple(color.upper() for color in spec.get("palette", ())),
    )
