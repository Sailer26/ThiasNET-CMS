"""Secondo fattore TOTP opzionale (D-28): segreto cifrato, niente riuso dei codici."""

from __future__ import annotations

import hmac
import re
from datetime import UTC, datetime

import pyotp

from app.extensions import db
from app.models.user import User
from app.services import audit
from app.services.crypto import decrypt_secret, encrypt_secret
from app.services.errors import ServiceError
from app.services.passwords import verify_password

ISSUER = "ThiasNET CMS"
VALID_WINDOW = 1  # un passo (30 s) prima o dopo: tollera orologi leggermente sfasati
BASE32_SECRET_RE = re.compile(r"[A-Z2-7]{16,64}")


def new_secret(user: User) -> tuple[str, str]:
    """Nuovo segreto e URI per il QR code. Non viene salvato finché non si conferma."""
    secret = pyotp.random_base32()
    return secret, pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=ISSUER)


def _matching_counter(secret: str, code: str, last_counter: int | None) -> int | None:
    totp = pyotp.TOTP(secret)
    now = totp.timecode(datetime.now(UTC))
    for counter in range(now - VALID_WINDOW, now + VALID_WINDOW + 1):
        if last_counter is not None and counter <= last_counter:
            continue  # codice già usato (o più vecchio): niente replay
        if hmac.compare_digest(totp.generate_otp(counter), code):
            return counter
    return None


def verify_code(user: User, code: str) -> bool:
    """Verifica il codice e ne impedisce il riuso. Il commit lo fa il chiamante."""
    if user.totp_secret_enc is None:
        return False
    counter = _matching_counter(decrypt_secret(user.totp_secret_enc), code, user.totp_last_counter)
    if counter is None:
        return False
    user.totp_last_counter = counter
    return True


def _require_password(user: User, password: str) -> None:
    if not verify_password(user.password_hash, password):
        raise ServiceError("invalid_password", "Password non corretta", 401)


def enable(user: User, *, secret: str, code: str, password: str) -> None:
    if user.totp_enabled:
        raise ServiceError("totp_already_enabled", "Il codice a 6 cifre è già attivo", 409)
    if not BASE32_SECRET_RE.fullmatch(secret):
        raise ServiceError("invalid_secret", "Configurazione non valida: ricomincia", 422)
    _require_password(user, password)
    counter = _matching_counter(secret, code, None)
    if counter is None:
        raise ServiceError("invalid_code", "Codice non valido", 401)
    user.totp_secret_enc = encrypt_secret(secret)
    user.totp_last_counter = counter
    audit.record("totp.enabled", actor_id=user.id, entity="user", entity_id=user.id)
    db.session.commit()


def disable(user: User, *, password: str, code: str) -> None:
    _require_password(user, password)
    if not verify_code(user, code):
        raise ServiceError("invalid_code", "Codice non valido", 401)
    user.totp_secret_enc = None
    user.totp_last_counter = None
    audit.record("totp.disabled", actor_id=user.id, entity="user", entity_id=user.id)
    db.session.commit()
