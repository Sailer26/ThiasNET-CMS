"""Anteprima (D-55): il documento salvato o quello inviato dal pannello, mai scritto.

Il documento inviato con il form passa dalla stessa validazione dell'autosave (modalità
bozza): ciò che si vede nell'anteprima è ciò che verrebbe salvato.
"""

from __future__ import annotations

import json
from typing import Any

from app.models.page import Page
from app.services import drafts
from app.services.blocks import Mode
from app.services.content import MAX_DOCUMENT_BYTES, validate_document
from app.services.errors import ServiceError
from app.services.theme import active_theme


def _reject_constant(constant: str) -> Any:
    raise ValueError(f"valore {constant} non ammesso")


def stored_document(page: Page) -> dict[str, Any]:
    data: dict[str, Any] = drafts.view(page)["data"]
    return data


def posted_document(raw: str | None) -> dict[str, Any]:
    if raw is None or not raw.strip():
        raise ServiceError("invalid_content", "Manca il contenuto da mostrare", 422)
    if len(raw.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise ServiceError("content_too_large", "La pagina è troppo grande per l'anteprima", 413)
    try:
        document = json.loads(raw, parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        raise ServiceError("invalid_content", "Contenuto dell'anteprima non valido", 422) from None
    return validate_document(active_theme(), document, Mode.DRAFT)
