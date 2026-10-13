"""Tentativi su credenziali (password o codice): controllo del limite e registrazione degli
errori, condivisi da login, cambio password e TOTP."""

from __future__ import annotations

from flask import request

from app.services import audit, rate_limit
from app.services.errors import ServiceError

TOO_MANY = "Troppi tentativi: riprova tra qualche minuto"


def client_ip() -> str | None:
    return request.remote_addr


def _too_many(wait: int) -> ServiceError:
    return ServiceError("rate_limited", TOO_MANY, 429, retry_after=wait)


def ensure_allowed(email: str) -> None:
    wait = rate_limit.retry_after(email, client_ip())
    if wait is not None:
        raise _too_many(wait)


def ensure_totp_allowed(email: str, user_id: int) -> None:
    """Il codice a 6 cifre ha anche un limite per account, che il login NON azzera."""
    ensure_allowed(email)
    wait = rate_limit.totp_retry_after(user_id)
    if wait is not None:
        raise _too_many(wait)


def record_failure(email: str, user_id: int | None, action: str) -> None:
    """L'email digitata non finisce mai nell'audit (a volte contiene la password)."""
    audit.record(action, actor_id=user_id)
    rate_limit.register_failure(email, client_ip())  # salva anche la riga di audit


def record_totp_failure(email: str, user_id: int, action: str) -> None:
    audit.record(action, actor_id=user_id)
    rate_limit.register_totp_failure(user_id, client_ip())
    rate_limit.register_failure(email, client_ip())
