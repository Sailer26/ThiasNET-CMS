"""Limite ai tentativi di login, salvato nel database (D-24).

Il database è condiviso da tutti i worker gunicorn, quindi il limite vale per l'istanza intera
senza Redis. L'account non viene mai bloccato del tutto: si limita la coppia email+IP e l'IP,
così un attaccante non può chiudere fuori il cliente.
"""

from __future__ import annotations

import ipaddress
import math
from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, and_, delete, select

from app.extensions import db
from app.models.login_attempt import LoginAttempt
from app.services.crypto import keyed_hash

WINDOW = timedelta(minutes=15)
MAX_PER_EMAIL_IP = 5
MAX_PER_IP = 30
MAX_TOTP_PER_USER = 5
RETENTION = timedelta(hours=24)
IPV6 = 6
IPV6_PREFIX = 64
TOTP_IP_KEY = "totp"


def _now() -> datetime:
    return datetime.now(UTC)


def _ip_bucket(ip: str | None) -> str:
    """IPv6: si conta per rete /64, perché chiunque ne ha miliardi di indirizzi a disposizione."""
    if not ip:
        return "-"
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if address.version == IPV6:
        return str(ipaddress.ip_network(f"{address}/{IPV6_PREFIX}", strict=False))
    return str(address)


def _ip_key(ip: str | None) -> str:
    return keyed_hash(_ip_bucket(ip), "login-ip-v1")


def _keys(email: str, ip: str | None) -> tuple[str, str]:
    return keyed_hash(email.strip().lower(), "login-email-v1"), _ip_key(ip)


def _totp_key(user_id: int) -> str:
    return keyed_hash(str(user_id), "totp-user-v1")


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
    """Dopo un accesso completo si azzera il contatore di quella email da quell'IP.
    Non fa commit: lo fa il chiamante insieme al login."""
    email_key, ip_key = _keys(email, ip)
    db.session.execute(
        delete(LoginAttempt).where(
            LoginAttempt.email_key == email_key, LoginAttempt.ip_key == ip_key
        )
    )


# --- Codice TOTP: limite per account (review sicurezza Fase 1) -------------------
# Separato dal limite email+IP: rifare login con la password giusta non lo azzera,
# quindi chi conosce la password non può provare codici all'infinito.


def totp_retry_after(user_id: int) -> int | None:
    return _wait_seconds(LoginAttempt.email_key == _totp_key(user_id), MAX_TOTP_PER_USER, _now())


def register_totp_failure(user_id: int, ip: str | None) -> None:
    # ip_key fittizio: questi tentativi sono già contati anche nel limite per IP.
    db.session.add(
        LoginAttempt(email_key=_totp_key(user_id), ip_key=TOTP_IP_KEY, created_at=_now())
    )
    db.session.commit()


def clear_totp(user_id: int) -> None:
    """Solo dopo un codice corretto. Non fa commit: lo fa il chiamante."""
    db.session.execute(delete(LoginAttempt).where(LoginAttempt.email_key == _totp_key(user_id)))
