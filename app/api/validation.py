"""Validazione dell'input delle API: mai fidarsi del client (CLAUDE.md)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import request
from jsonschema import Draft202012Validator

from app.services.errors import ServiceError

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


def _invalid(message: str) -> ServiceError:
    return ServiceError("invalid_body", message, 422)


def json_body(schema: Mapping[str, Any]) -> dict[str, Any]:
    try:
        data = request.get_json(silent=True)
    except RecursionError:  # annidamento enorme: silent cattura solo ValueError
        data = None
    if not isinstance(data, dict):
        raise _invalid("Il corpo della richiesta deve essere un oggetto JSON")
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: e.json_path)
    if errors:
        where = ".".join(str(p) for p in errors[0].absolute_path) or "richiesta"
        raise _invalid(f"Dato non valido in '{where}'")
    return data


def pagination() -> tuple[int, int]:
    """`?page=1&limit=25` con limiti stretti: niente query senza confini."""
    try:
        page = int(request.args.get("page", "1"))
        limit = int(request.args.get("limit", str(DEFAULT_PAGE_SIZE)))
    except ValueError:
        raise _invalid("Parametri di paginazione non validi") from None
    if page < 1 or not 1 <= limit <= MAX_PAGE_SIZE:
        raise _invalid(f"La pagina parte da 1 e il limite va da 1 a {MAX_PAGE_SIZE}")
    return page, limit


def page_meta(page: int, limit: int, total: int) -> dict[str, int]:
    return {"page": page, "limit": limit, "total": total}
