"""Secondo fattore TOTP opzionale (D-28): segreto generato dal server e cifrato,
niente riuso dei codici, tentativi limitati."""

from __future__ import annotations

import hmac
import logging
from datetime import UTC, datetime
from typing import Any, cast

import pyotp
from cryptography.fernet import InvalidToken
from flask import session
from sqlalchemy import CursorResult, or_, update
from sqlalchemy.orm.attributes import set_committed_value

from app.extensions import db
from app.models.user import User
from app.services import audit
from app.services.attempts import ensure_totp_allowed, record_totp_failure
from app.services.crypto import decrypt_secret, encrypt_secret
from app.services.errors import ServiceError
from app.services.passwords import verify_password

logger = logging.getLogger(__name__)

ISSUER = "ThiasNET CMS"
VALID_WINDOW = 1  # un passo (30 s) prima o dopo: tollera orologi leggermente sfasati
SETUP_KEY = "totp_setup"


def _wrong_credentials() -> ServiceError:
    """Un solo messaggio: non rivela se è sbagliata la password o il codice."""
    return ServiceError("invalid_credentials", "Password o codice non corretti", 401)


def begin_setup(user: User) -> tuple[str, str]:
    """Il segreto lo genera il server e resta in sessione finché non si conferma:
    il client non può imporne uno debole (review sicurezza Fase 1)."""
    secret = pyotp.random_base32()
    session[SETUP_KEY] = secret
    return secret, pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=ISSUER)


def _matching_counter(secret: str, code: str, last_counter: int | None) -> int | None:
    generator = pyotp.TOTP(secret)
    now = generator.timecode(datetime.now(UTC))
    for counter in range(now - VALID_WINDOW, now + VALID_WINDOW + 1):
        if last_counter is not None and counter <= last_counter:
            continue  # codice già usato (o più vecchio): niente replay
        if hmac.compare_digest(generator.generate_otp(counter), code):
            return counter
    return None


def _decrypt(user: User) -> str:
    try:
        return decrypt_secret(user.totp_secret_enc or "")
    except InvalidToken:
        # Succede se SECRET_KEY è cambiata: va disattivato e riattivato (`flask disable-totp`).
        logger.error("Segreto TOTP non decifrabile per l'utente %s", user.id)
        raise ServiceError(
            "totp_unreadable",
            "Il codice a 6 cifre non è più verificabile: chiedi all'amministratore "
            "di disattivarlo, poi riattivalo",
            409,
        ) from None


def _consume_counter(user: User, counter: int) -> bool:
    """Aggiornamento atomico: tra due richieste parallele con lo stesso codice ne passa una."""
    result = db.session.execute(
        update(User)
        .where(
            User.id == user.id,
            or_(User.totp_last_counter.is_(None), User.totp_last_counter < counter),
        )
        .values(totp_last_counter=counter)
        .execution_options(synchronize_session=False)
    )
    if cast(CursorResult[Any], result).rowcount != 1:
        return False
    set_committed_value(user, "totp_last_counter", counter)
    return True


def verify_code(user: User, code: str) -> bool:
    """Verifica il codice e ne impedisce il riuso. Il commit lo fa il chiamante."""
    if user.totp_secret_enc is None:
        return False
    counter = _matching_counter(_decrypt(user), code, user.totp_last_counter)
    return counter is not None and _consume_counter(user, counter)


def enable(user: User, *, code: str, password: str) -> None:
    if user.totp_enabled:
        raise ServiceError("totp_already_enabled", "Il codice a 6 cifre è già attivo", 409)
    secret = session.get(SETUP_KEY)
    if not isinstance(secret, str):
        raise ServiceError("totp_setup_missing", "Ricomincia la configurazione del codice", 409)
    ensure_totp_allowed(user.email, user.id)
    counter = _matching_counter(secret, code, None)
    if not verify_password(user.password_hash, password) or counter is None:
        record_totp_failure(user.email, user.id, "totp.enable_failed")
        raise _wrong_credentials()
    session.pop(SETUP_KEY, None)
    user.totp_secret_enc = encrypt_secret(secret)
    user.totp_last_counter = counter
    audit.record("totp.enabled", actor_id=user.id, entity="user", entity_id=user.id)
    db.session.commit()


def disable(user: User, *, password: str, code: str) -> None:
    ensure_totp_allowed(user.email, user.id)
    password_ok = verify_password(user.password_hash, password)
    if not password_ok or not verify_code(user, code):
        record_totp_failure(user.email, user.id, "totp.disable_failed")
        raise _wrong_credentials()
    user.totp_secret_enc = None
    user.totp_last_counter = None
    audit.record("totp.disabled", actor_id=user.id, entity="user", entity_id=user.id)
    db.session.commit()
