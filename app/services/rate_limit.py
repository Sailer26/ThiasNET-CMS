"""Limite ai tentativi di login, salvato nel database (D-24).

Il database è condiviso da tutti i worker gunicorn, quindi il limite vale per l'istanza intera
senza Redis. L'account non viene mai bloccato del tutto: si limita la coppia email+IP e l'IP,
così un attaccante non può chiudere fuori il cliente.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, and_, delete, select

from app.extensions import db
from app.models.login_attempt import LoginAttempt
from app.services.crypto import keyed_hash

WINDOW = timedelta(minutes=15)
MAX_PER_EMAIL_IP = 5
MAX_PER_IP = 30
RETENTION = timedelta(hours=24)


def _now() -> datetime:
    return datetime.now(UTC)


def _keys(email: str, ip: str | None) -> tuple[str, str]:
    return (
        keyed_hash(email.strip().lower(), "login-email-v1"),
        keyed_hash(ip or "-", "login-ip-v1"),
    )


def _wait_seconds(condition: ColumnElement[bool], limit: int, now: datetime) -> int | None:
    recent = db.session.execute(
        select(LoginAttempt.created_at)
        .where(condition, LoginAttempt.created_at >= now - WINDOW)
        .order_by(LoginAttempt.created_at.desc())
        .limit(limit)
    ).scalars()
    times = list(recent)
    if len(times) < limit:
        return None
    # Il blocco dura finché il più vecchio degli ultimi `limit` tentativi esce dalla finestra.
    return max(1, math.ceil((times[-1] + WINDOW - now).total_seconds()))


def retry_after(email: str, ip: str | None) -> int | None:
    """Secondi da attendere, oppure None se si può tentare."""
    email_key, ip_key = _keys(email, ip)
    now = _now()
    by_pair = and_(LoginAttempt.email_key == email_key, LoginAttempt.ip_key == ip_key)
    return _wait_seconds(by_pair, MAX_PER_EMAIL_IP, now) or _wait_seconds(
        LoginAttempt.ip_key == ip_key, MAX_PER_IP, now
    )


def register_failure(email: str, ip: str | None) -> None:
    """Registra un tentativo fallito e salva subito (anche se la richiesta poi fallisce)."""
    email_key, ip_key = _keys(email, ip)
    now = _now()
    db.session.execute(delete(LoginAttempt).where(LoginAttempt.created_at < now - RETENTION))
    db.session.add(LoginAttempt(email_key=email_key, ip_key=ip_key, created_at=now))
    db.session.commit()


def clear(email: str, ip: str | None) -> None:
    """Dopo un accesso riuscito si azzera il contatore di quella email da quell'IP."""
    email_key, ip_key = _keys(email, ip)
    db.session.execute(
        delete(LoginAttempt).where(
            LoginAttempt.email_key == email_key, LoginAttempt.ip_key == ip_key
        )
    )
