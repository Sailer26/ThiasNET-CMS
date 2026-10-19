"""Campi delle impostazioni (D-14, D-143): dati del sito fissi, aspetto da `theme.json`.

Da qui escono lo schema per il pannello (le stesse parole chiave dei blocchi, D-106) e la
validazione del server. I valori sono solo dati: niente CSS, JS, HTML o template, e una
chiave che il tema non dichiara è un errore (regola d'oro).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from app.extensions import db
from app.models.media import Media, MediaKind
from app.services.blocks import FieldError
from app.services.sanitize import clean_line, clean_plain, is_safe_url, normalize_url
from app.services.theme import Theme

HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
# Un solo indirizzo semplice e solo ASCII, come per il modulo contatti (D-61).
EMAIL_RE = re.compile(
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+"
)
EMAIL_MAX_LENGTH = 254
URL_MAX_LENGTH = 2048
MAX_ID = 2**31 - 1  # oltre, SQLite non lo sa nemmeno confrontare (errore 500)
TEXT_MAX_LENGTH = 2000  # testi del tema senza "max"


@dataclass(frozen=True)
class Field:
    key: str
    type: str  # text, textarea, email, boolean, select, color, url, media
    label: str
    max: int | None = None
    options: tuple[str, ...] = ()
    palette: tuple[str, ...] = ()
    help: str = ""
    required: bool = False
    https_only: bool = False
    default: Any = None


def _social(key: str, label: str) -> Field:
    return Field(
        key,
        "url",
        label,
        help=f"Indirizzo completo della pagina {label} (https://…).",
        https_only=True,
    )


# D-143: Matomo, favicon e SITE_URL restano nella configurazione di Thias.
SITE_FIELDS: tuple[Field, ...] = (
    Field(
        "name",
        "text",
        "Nome del sito",
        max=120,
        required=True,
        help="Compare in alto e nel titolo delle pagine.",
    ),
    Field(
        "logo", "media", "Logo", help="Un'immagine con il testo alternativo (di solito il nome)."
    ),
    Field("email", "email", "Email di contatto", max=EMAIL_MAX_LENGTH),
    Field("phone", "text", "Telefono", max=30),
    Field("address", "textarea", "Indirizzo", max=300),
    _social("facebook", "Facebook"),
    _social("instagram", "Instagram"),
    _social("linkedin", "LinkedIn"),
    _social("youtube", "YouTube"),
    Field(
        "contact_recipient",
        "email",
        "Email che riceve i messaggi del sito",
        max=EMAIL_MAX_LENGTH,
        help=(
            "Qui arrivano i messaggi del modulo contatti. "
            "Se la lasci vuota, vanno all'indirizzo impostato da ThiasNET."
        ),
    ),
)
SOCIAL_KEYS = ("facebook", "instagram", "linkedin", "youtube")


def theme_fields(theme: Theme) -> tuple[Field, ...]:
    return tuple(
        Field(
            key,
            spec.type,
            spec.label,
            max=spec.max,
            options=spec.options,
            palette=tuple(color.upper() for color in spec.palette),
            default=spec.default,
        )
        for key, spec in theme.settings.items()
    )


# --- Schema per il pannello ---------------------------------------------------------------


def _field_schema(field: Field) -> dict[str, Any]:
    result: dict[str, Any] = {"title": field.label}
    if field.help:
        result["description"] = field.help
    if field.type in {"text", "textarea", "email"}:
        result.update(type="string", maxLength=field.max or TEXT_MAX_LENGTH)
    elif field.type == "boolean":
        result["type"] = "boolean"
    elif field.type == "select":
        result.update(type="string", enum=list(field.options))
    elif field.type == "color" and field.palette:
        result.update({"type": "string", "enum": list(field.palette), "x-color": True})
    elif field.type == "color":
        result.update(type="string", pattern=HEX_COLOR_RE.pattern, maxLength=7)
    elif field.type == "url":
        result.update(type="string", format="safe-url", maxLength=URL_MAX_LENGTH)
    elif field.type == "media":
        result.update({"type": "integer", "minimum": 1, "maximum": MAX_ID, "x-media": "image"})
    return result


def schema(fields: Iterable[Field]) -> dict[str, Any]:
    found = tuple(fields)
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {field.key: _field_schema(field) for field in found},
        "required": [field.key for field in found if field.required],
    }


# --- Validazione --------------------------------------------------------------------------


def _text(field: Field, value: Any) -> tuple[Any, str | None]:
    if not isinstance(value, str):
        return None, "invalid_type"
    cleaned = clean_plain(value) if field.type == "textarea" else clean_line(value)
    if len(cleaned) > (field.max or TEXT_MAX_LENGTH):
        return None, "max_length"
    bad_email = len(cleaned) > EMAIL_MAX_LENGTH or not EMAIL_RE.fullmatch(cleaned)
    if field.type == "email" and cleaned and bad_email:
        return None, "invalid_email"
    return cleaned or None, None


def _url(field: Field, value: Any) -> tuple[Any, str | None]:
    if not isinstance(value, str):
        return None, "invalid_type"
    url = normalize_url(value.strip())
    if not url:
        return None, None
    if len(url) > URL_MAX_LENGTH or not is_safe_url(url):
        return None, "invalid_url"
    if field.https_only and not url.startswith("https://"):
        return None, "invalid_url"
    return url, None


def _color(field: Field, value: Any) -> tuple[Any, str | None]:
    if not isinstance(value, str):
        return None, "invalid_type"
    if not HEX_COLOR_RE.fullmatch(value):
        return None, "invalid_color"
    color = value.upper()
    if field.palette and color not in field.palette:
        return None, "not_in_palette"
    return color, None


def check(field: Field, value: Any) -> tuple[Any, str | None]:
    """Valore pulito (None = predefinito) e codice d'errore; senza database."""
    if value is None:
        return None, None
    if field.type in {"text", "textarea", "email"}:
        return _text(field, value)
    if field.type == "url":
        return _url(field, value)
    if field.type == "color":
        return _color(field, value)
    if field.type == "boolean":
        return (value, None) if isinstance(value, bool) else (None, "invalid_type")
    if field.type == "select":
        if not isinstance(value, str):
            return None, "invalid_type"
        return (value, None) if value in field.options else (None, "not_in_options")
    if field.type == "media":
        valid = isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= MAX_ID
        return (value, None) if valid else (None, "invalid_type")
    return None, "invalid_type"


MESSAGES = {
    "unknown": "Impostazione sconosciuta",
    "required": "Campo obbligatorio",
    "max_length": "Testo troppo lungo",
    "invalid_type": "Valore non valido",
    "invalid_email": "Indirizzo email non valido",
    "invalid_url": "Indirizzo non valido (serve https:// per i social)",
    "invalid_color": "Colore non valido",
    "not_in_palette": "Colore non previsto dal tema",
    "not_in_options": "Scelta non prevista dal tema",
    "media_missing": "Il file non c'è più nella libreria",
    "media_not_image": "Qui serve un'immagine",
    "alt_missing": "Aggiungi il testo alternativo all'immagine (nella libreria)",
}


def _media_problem(media_id: int) -> str | None:
    """Come per le pagine (D-77): un'immagine sul sito ha sempre il testo alternativo."""
    found = db.session.execute(select(Media.kind, Media.alt).where(Media.id == media_id)).first()
    if found is None:
        return "media_missing"
    kind, alt = found
    if kind != MediaKind.IMAGE:
        return "media_not_image"
    return None if alt.strip() else "alt_missing"


def validate(
    fields: Iterable[Field], values: Mapping[str, Any]
) -> tuple[dict[str, Any], list[FieldError]]:
    by_key = {field.key: field for field in fields}
    errors = [
        FieldError(key, "unknown", MESSAGES["unknown"]) for key in values if key not in by_key
    ]
    clean: dict[str, Any] = {}
    for key, field in by_key.items():
        value, problem = check(field, values.get(key))
        if problem is None and value is None and field.required:
            problem = "required"
        if problem is None and field.type == "media" and value is not None:
            problem = _media_problem(value)
        if problem is not None:
            errors.append(FieldError(key, problem, MESSAGES[problem]))
        elif value is not None:
            clean[key] = value
    return clean, errors


def lenient(fields: Iterable[Field], values: Mapping[str, Any]) -> dict[str, Any]:
    """Valori salvati ancora validi per i campi di oggi (dopo un cambio di tema i vecchi o
    sbagliati valgono il predefinito, D-53); senza database."""
    found: dict[str, Any] = {}
    for field in fields:
        value, problem = check(field, values.get(field.key))
        if problem is None and value is not None:
            found[field.key] = value
    return found
