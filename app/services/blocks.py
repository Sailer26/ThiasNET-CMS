"""Registry dei blocchi: uno schema JSON per ognuno dei 13 tipi base (D-11, D-46).

Gli schemi stanno in `app/blocks/<tipo>.schema.json` e si caricano all'avvio: se mancano,
sono in più o non sono validi, l'app non parte. Annotazioni proprie:
- `x-richtext`: stringa HTML da ripulire con nh3 (tutte le altre sono testo semplice);
- `x-media`: id di un media (intero >= 1), esistenza verificata dalla Fase 4;
- formato `safe-url`: http(s), mailto, tel o percorso del sito;
- `title`/`description` dei campi e `x-enum-titles`: etichette italiane del pannello (D-106).
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from app.core_types import BLOCK_TYPES
from app.services.sanitize import clean_plain, clean_rich, is_safe_url, normalize_url

BLOCKS_DIR = Path(__file__).resolve().parents[1] / "blocks"
SCHEMA_SUFFIX = ".schema.json"
# In bozza (D-46) i campi obbligatori possono ancora mancare; "if" resta intatto perché
# serve a scegliere il ramo giusto (es. il formato dell'id video per provider).
PUBLISH_ONLY_KEYWORDS = frozenset({"required", "minItems", "dependentRequired"})
# Le stringhe con enum non hanno maxLength: nessun valore ammesso è così lungo.
MAX_UNBOUNDED_STRING = 256

FORMAT_CHECKER = FormatChecker(formats=())


@FORMAT_CHECKER.checks("safe-url")
def _check_safe_url(value: object) -> bool:
    return not isinstance(value, str) or is_safe_url(value)


class BlockRegistryError(RuntimeError):
    """Schemi dei blocchi mancanti o non validi: l'app non deve partire."""


class Mode(StrEnum):
    DRAFT = "draft"
    PUBLISH = "publish"


@dataclass(frozen=True)
class FieldError:
    path: str
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "code": self.code, "message": self.message}


def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def _message(error: ValidationError) -> str:
    value: Any = error.validator_value
    messages = {
        "required": "Campo obbligatorio",
        "dependentRequired": "Compila anche questo campo",
        "additionalProperties": "Campo non previsto",
        "type": "Tipo di dato non valido",
        "enum": "Valore non ammesso",
        "const": "Valore non ammesso",
        "pattern": "Formato non valido",
        "format": "Indirizzo non valido: usa https://, mailto:, tel: o un percorso con /",
    }
    if error.validator in messages:
        return messages[str(error.validator)]
    if error.validator == "maxLength":
        return f"Al massimo {value} caratteri"
    if error.validator == "maxItems":
        return f"Al massimo {value} {_plural(value, 'elemento', 'elementi')}"
    if error.validator == "minItems":
        return f"Aggiungi almeno {value} {_plural(value, 'elemento', 'elementi')}"
    if error.validator == "minimum":
        return f"Il valore minimo è {value}"
    if error.validator == "maximum":
        return f"Il valore massimo è {value}"
    return "Dato non valido"


def join_path(*parts: object) -> str:
    """Percorso di un campo nel formato del pannello: "zones/main/0/data/title"."""
    return "/".join(str(part) for part in parts if part != "")


def _error_paths(error: ValidationError, prefix: str) -> Iterator[str]:
    """Percorso del campo interessato: per required e simili è il campo mancante o in più."""
    base = join_path(prefix, *error.absolute_path)
    instance = error.instance if isinstance(error.instance, dict) else {}
    value: Any = error.validator_value
    schema: Any = error.schema
    if error.validator == "required":
        yield from (join_path(base, n) for n in value if n not in instance)
    elif error.validator == "dependentRequired":
        for name, deps in value.items():
            if name in instance:
                yield from (join_path(base, dep) for dep in deps if dep not in instance)
    elif error.validator == "additionalProperties":
        known = schema.get("properties", {})
        yield from (join_path(base, name) for name in instance if name not in known)
    else:
        yield base


def schema_errors(validator: Draft202012Validator, data: Any, prefix: str) -> list[FieldError]:
    """Errori di uno schema JSON come FieldError in italiano, ordinati e senza doppioni."""
    found = {
        FieldError(path, str(error.validator), _message(error))
        for error in validator.iter_errors(data)
        for path in _error_paths(error, prefix)
    }
    return sorted(found, key=lambda e: (e.path, e.code))


def _without_publish_rules(schema: Any) -> Any:
    """Copia dello schema per la bozza. Dentro "properties" le chiavi sono nomi di campi
    (un campo può chiamarsi "required"): si filtrano solo le parole chiave dello schema."""
    if isinstance(schema, dict):
        result: dict[str, Any] = {}
        for key, value in schema.items():
            if key in PUBLISH_ONLY_KEYWORDS:
                continue
            if key == "if":
                result[key] = value
            elif key == "properties" and isinstance(value, dict):
                result[key] = {name: _without_publish_rules(sub) for name, sub in value.items()}
            else:
                result[key] = _without_publish_rules(value)
        return result
    if isinstance(schema, list):
        return [_without_publish_rules(item) for item in schema]
    return schema


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


def _clean_value(schema: Mapping[str, Any], value: Any) -> Any:
    """Pulisce le stringhe previste dallo schema; i tipi sbagliati restano alla validazione.
    Le stringhe vuote dopo la pulizia contano come campo assente."""
    kind = schema.get("type")
    if kind == "string" and isinstance(value, str):
        if len(value) > schema.get("maxLength", MAX_UNBOUNDED_STRING):
            return value  # troppo lunga: la boccia la validazione, senza passarla a nh3
        if schema.get("x-richtext"):
            return clean_rich(value)
        if schema.get("format") == "safe-url":
            return normalize_url(clean_plain(value))
        return clean_plain(value)
    if kind == "object" and isinstance(value, dict):
        properties = schema.get("properties", {})
        result: dict[str, Any] = {}
        for key, item in value.items():
            cleaned = _clean_value(properties[key], item) if key in properties else item
            if cleaned != "":
                result[key] = cleaned
        return result
    if kind == "array" and isinstance(value, list) and "items" in schema:
        return [_clean_value(schema["items"], item) for item in value]
    return value


@dataclass(frozen=True)
class MediaRef:
    """Un media usato da un blocco: id, tipo richiesto ("image" o "file") e campo."""

    media_id: int
    kind: str
    path: str


def _media_refs(schema: Mapping[str, Any], value: Any, path: str) -> Iterator[MediaRef]:
    """Accetta anche le strutture congelate del renderer (MappingProxyType, tuple)."""
    kind = schema.get("x-media")
    if kind and isinstance(value, int) and not isinstance(value, bool):
        yield MediaRef(value, str(kind), path)
    elif isinstance(value, Mapping):
        for key, sub in schema.get("properties", {}).items():
            if key in value:
                yield from _media_refs(sub, value[key], join_path(path, key))
    elif isinstance(value, Sequence) and not isinstance(value, str) and "items" in schema:
        for index, item in enumerate(value):
            yield from _media_refs(schema["items"], item, join_path(path, index))


@dataclass(frozen=True)
class _Entry:
    schema: Mapping[str, Any]
    validators: Mapping[Mode, Draft202012Validator]


class BlockRegistry:
    """Registro immutabile dei tipi di blocco."""

    def __init__(self, schemas: Mapping[str, dict[str, Any]]) -> None:
        self._entries: Mapping[str, _Entry] = MappingProxyType(
            {
                name: _Entry(
                    schema=_freeze(schema),
                    validators=MappingProxyType(
                        {
                            Mode.PUBLISH: Draft202012Validator(
                                schema, format_checker=FORMAT_CHECKER
                            ),
                            Mode.DRAFT: Draft202012Validator(
                                _without_publish_rules(schema), format_checker=FORMAT_CHECKER
                            ),
                        }
                    ),
                )
                for name, schema in schemas.items()
            }
        )

    @property
    def types(self) -> frozenset[str]:
        return frozenset(self._entries)

    def schema(self, block_type: str) -> Mapping[str, Any]:
        return self._entries[block_type].schema

    def clean(self, block_type: str, data: Any) -> Any:
        entry = self._entries.get(block_type)
        return data if entry is None else _clean_value(entry.schema, data)

    def errors(
        self, block_type: str, data: Any, mode: Mode, prefix: str = "data"
    ) -> list[FieldError]:
        entry = self._entries.get(block_type)
        if entry is None:
            return [FieldError("type", "unknown_type", "Tipo di blocco sconosciuto")]
        return schema_errors(entry.validators[mode], data, prefix)

    def media_refs(self, block_type: str, data: Any, prefix: str = "data") -> tuple[MediaRef, ...]:
        entry = self._entries.get(block_type)
        return () if entry is None else tuple(_media_refs(entry.schema, data, prefix))

    def media_ids(self, block_type: str, data: Any) -> tuple[int, ...]:
        return tuple(ref.media_id for ref in self.media_refs(block_type, data))


def _check_labels(schema: Mapping[str, Any], name: str, prefix: str = "") -> None:
    """D-106: ogni campo ha un'etichetta italiana; ogni enum le sue etichette, una per valore."""
    for field, spec in schema.get("properties", {}).items():
        where = f"{name}.{prefix}{field}"
        if not isinstance(spec.get("title"), str) or not spec["title"].strip():
            raise BlockRegistryError(f"Schema del blocco '{where}': manca l'etichetta (title)")
        titles = spec.get("x-enum-titles")
        if "enum" in spec and (not isinstance(titles, list) or len(titles) != len(spec["enum"])):
            raise BlockRegistryError(
                f"Schema del blocco '{where}': x-enum-titles deve avere un'etichetta per valore"
            )
        if spec.get("type") == "array" and isinstance(spec.get("items"), Mapping):
            _check_labels(spec["items"], name, f"{prefix}{field}.")


def _read_schema(path: Path, name: str) -> dict[str, Any]:
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except (json.JSONDecodeError, UnicodeDecodeError, SchemaError) as exc:
        raise BlockRegistryError(f"Schema del blocco '{name}' non valido: {exc}") from exc
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        raise BlockRegistryError(f"Schema del blocco '{name}': serve un oggetto chiuso")
    _check_labels(schema, name)
    return dict(schema)


def load_registry(directory: Path) -> BlockRegistry:
    files = {p.name.removesuffix(SCHEMA_SUFFIX): p for p in directory.glob(f"*{SCHEMA_SUFFIX}")}
    missing, unknown = BLOCK_TYPES - files.keys(), files.keys() - BLOCK_TYPES
    if missing or unknown:
        raise BlockRegistryError(
            f"Schemi dei blocchi non allineati a BLOCK_TYPES: mancanti {sorted(missing)}, "
            f"sconosciuti {sorted(unknown)}"
        )
    return BlockRegistry({name: _read_schema(path, name) for name, path in sorted(files.items())})


_REGISTRY = load_registry(BLOCKS_DIR)


def get_registry() -> BlockRegistry:
    return _REGISTRY
