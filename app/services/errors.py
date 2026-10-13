"""Errore di dominio unico: le route lo trasformano nella risposta JSON standard."""

from __future__ import annotations


class ServiceError(Exception):
    """Errore previsto, con messaggio in italiano mostrabile all'utente."""

    def __init__(
        self, code: str, message: str, status: int, *, retry_after: int | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.retry_after = retry_after


def forbidden() -> ServiceError:
    return ServiceError("forbidden", "Non hai i permessi per questa operazione", 403)


def not_found(message: str = "Risorsa non trovata") -> ServiceError:
    return ServiceError("not_found", message, 404)
