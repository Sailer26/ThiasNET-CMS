"""Errore di dominio unico: le route lo trasformano nella risposta JSON standard."""

from __future__ import annotations

from datetime import datetime
from typing import Any


class ServiceError(Exception):
    """Errore previsto, con messaggio in italiano mostrabile all'utente."""

    def __init__(
        self,
        code: str,
        message: str,
        status: int,
        *,
        retry_after: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.retry_after = retry_after
        self.details = details  # es. i campi non validi, mostrati accanto al campo nel pannello


def forbidden() -> ServiceError:
    return ServiceError("forbidden", "Non hai i permessi per questa operazione", 403)


def not_found(message: str = "Risorsa non trovata") -> ServiceError:
    return ServiceError("not_found", message, 404)


def version_conflict(
    current_version: int,
    updated_by: int | None,
    updated_at: datetime | None,
    subject: str = "questa pagina",
) -> ServiceError:
    """Blocco ottimistico (D-44): qualcun altro ha salvato nel frattempo. Il nome di chi
    ha salvato serve al pannello anche per chi non può leggere gli utenti (D-92)."""
    from app.services.authors import display_name  # usa il database: import solo qui

    return ServiceError(
        "version_conflict",
        f"Qualcun altro ha modificato {subject}: ricarica per vedere le ultime modifiche",
        409,
        details={
            "current_version": current_version,
            "updated_by": updated_by,
            "updated_by_name": display_name(updated_by),
            "updated_at": updated_at.isoformat() if updated_at else None,
        },
    )
