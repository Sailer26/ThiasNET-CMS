"""Login, sessione, secondo fattore e cambio password (D-22, D-26, D-27, D-28)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flask import g, session
from flask_login import login_user, logout_user
from flask_wtf.csrf import generate_csrf

from app.extensions import db
from app.models.user import User
from app.services import audit, passwords, rate_limit, totp, users
from app.services.attempts import (
    client_ip,
    ensure_allowed,
    ensure_totp_allowed,
    record_failure,
    record_totp_failure,
)
from app.services.errors import ServiceError

PENDING_TOTP_TTL = timedelta(minutes=5)
# La sessione dura 12 ore e si rinnova usando il pannello, ma mai oltre questo tetto (D-27).
ABSOLUTE_SESSION_LIMIT = timedelta(days=7)
PENDING_KEY = "pending_2fa"
LOGIN_AT_KEY = "login_at"
INVALID_CREDENTIALS = "Email o password non corretti"


def _now() -> datetime:
    return datetime.now(UTC)


def _invalid() -> ServiceError:
    return ServiceError("invalid_credentials", INVALID_CREDENTIALS, 401)


def _session_expired() -> bool:
    login_at = session.get(LOGIN_AT_KEY)
    if not isinstance(login_at, int | float):
        return True
    return _now().timestamp() - login_at > ABSOLUTE_SESSION_LIMIT.total_seconds()


def load_user(user_id: str) -> User | None:
    """`user_loader` di Flask-Login: l'id include la versione di sessione (D-26)."""
    try:
        raw_id, raw_version = user_id.split(":")
        numeric_id, version = int(raw_id), int(raw_version)
    except ValueError:
        return None
    if _session_expired():
        return None
    user = db.session.get(User, numeric_id)
    if user is None or not user.active or user.session_version != version:
        return None
    return user


def authenticate(email: str, password: str) -> User:
    """Verifica email e password. Stesso messaggio e stesso costo per email inesistenti."""
    email = email.strip().lower()
    ensure_allowed(email)
    user = users.get_by_email(email)
    if user is None or not user.active:
        passwords.verify_dummy(password)
        record_failure(email, user.id if user else None, "auth.login_failed")
        raise _invalid()
    if not passwords.verify_password(user.password_hash, password):
        record_failure(email, user.id, "auth.login_failed")
        raise _invalid()
    if passwords.needs_rehash(user.password_hash):
        user.password_hash = passwords.hash_password(password)
    if not user.totp_enabled:
        # Con il TOTP il contatore si azzera solo dopo il codice corretto: altrimenti
        # rifare login azzererebbe anche i tentativi sul codice (review sicurezza Fase 1).
        rate_limit.clear(email, client_ip())
    return user


def _fresh_session() -> None:
    """Nuova sessione a ogni cambio di stato: niente session fixation."""
    session.clear()
    g.pop("csrf_token", None)  # Flask-WTF tiene in `g` il token della sessione precedente


def _establish(user: User) -> str:
    _fresh_session()
    if not login_user(user):
        raise _invalid()
    session.permanent = True
    session[LOGIN_AT_KEY] = _now().timestamp()
    return str(generate_csrf())


def start_session(user: User) -> str:
    """Login completato. Restituisce il nuovo token CSRF per la SPA."""
    token = _establish(user)
    user.last_login_at = _now()
    audit.record("auth.login", actor_id=user.id)
    db.session.commit()
    return token


def begin_totp(user: User) -> str:
    """Password corretta ma serve il codice: l'utente NON è ancora loggato."""
    _fresh_session()
    session[PENDING_KEY] = {
        "uid": user.id,
        "ver": user.session_version,
        "exp": (_now() + PENDING_TOTP_TTL).timestamp(),
    }
    db.session.commit()
    return str(generate_csrf())


def complete_totp(code: str) -> User:
    pending = session.get(PENDING_KEY)
    if not pending:
        raise ServiceError("totp_not_started", "Accedi prima con email e password", 401)
    if _now().timestamp() > pending["exp"]:
        session.pop(PENDING_KEY, None)
        raise ServiceError("totp_expired", "Tempo scaduto: accedi di nuovo", 410)
    user = db.session.get(User, pending["uid"])
    if user is None or not user.active or user.session_version != pending["ver"]:
        session.pop(PENDING_KEY, None)
        raise _invalid()
    ensure_totp_allowed(user.email, user.id)
    if not totp.verify_code(user, code):
        record_totp_failure(user.email, user.id, "auth.totp_failed")
        raise ServiceError("invalid_code", "Codice non valido", 401)
    rate_limit.clear(user.email, client_ip())
    rate_limit.clear_totp(user.id)
    return user


def _end_session() -> str:
    """Chiude la sessione e ne apre una anonima: la SPA riceve subito un token valido."""
    logout_user()
    _fresh_session()
    return str(generate_csrf())


def logout(user: User) -> str:
    audit.record("auth.logout", actor_id=user.id)
    db.session.commit()
    return _end_session()


def logout_everywhere(user: User) -> str:
    user.session_version += 1
    audit.record("auth.logout_all", actor_id=user.id)
    db.session.commit()
    return _end_session()


def change_password(user: User, current: str, new: str) -> str:
    """Le altre sessioni vengono chiuse; quella corrente resta valida con un nuovo token."""
    users.check_password(new)
    ensure_allowed(user.email)
    if not passwords.verify_password(user.password_hash, current):
        record_failure(user.email, user.id, "auth.password_change_failed")
        raise ServiceError("invalid_password", "La password attuale non è corretta", 401)
    users.set_password(user, new)
    audit.record("auth.password_changed", actor_id=user.id, entity="user", entity_id=user.id)
    token = _establish(user)
    db.session.commit()
    return token
