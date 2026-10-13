"""Login, sessione, secondo fattore e cambio password (D-22, D-26, D-27, D-28)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flask import g, request, session
from flask_login import login_user, logout_user
from flask_wtf.csrf import generate_csrf

from app.extensions import db
from app.models.user import User
from app.services import audit, passwords, rate_limit, totp, users
from app.services.errors import ServiceError

PENDING_TOTP_TTL = timedelta(minutes=5)
PENDING_KEY = "pending_2fa"
INVALID_CREDENTIALS = "Email o password non corretti"


def _now() -> datetime:
    return datetime.now(UTC)


def _ip() -> str | None:
    return request.remote_addr


def _invalid() -> ServiceError:
    return ServiceError("invalid_credentials", INVALID_CREDENTIALS, 401)


def _check_rate_limit(email: str) -> None:
    wait = rate_limit.retry_after(email, _ip())
    if wait is not None:
        raise ServiceError(
            "rate_limited",
            "Troppi tentativi: riprova tra qualche minuto",
            429,
            retry_after=wait,
        )


def _fail(email: str, user_id: int | None, action: str) -> None:
    """L'email digitata non finisce mai nell'audit (a volte contiene la password)."""
    audit.record(action, actor_id=user_id)
    rate_limit.register_failure(email, _ip())  # salva anche la riga di audit


def load_user(user_id: str) -> User | None:
    """`user_loader` di Flask-Login: l'id include la versione di sessione (D-26)."""
    try:
        raw_id, raw_version = user_id.split(":")
        user = db.session.get(User, int(raw_id))
        version = int(raw_version)
    except ValueError:
        return None
    if user is None or not user.active or user.session_version != version:
        return None
    return user


def authenticate(email: str, password: str) -> User:
    """Verifica email e password. Stesso messaggio e stesso costo per email inesistenti."""
    email = email.strip().lower()
    _check_rate_limit(email)
    user = users.get_by_email(email)
    if user is None or not user.active:
        passwords.verify_dummy(password)
        _fail(email, user.id if user else None, "auth.login_failed")
        raise _invalid()
    if not passwords.verify_password(user.password_hash, password):
        _fail(email, user.id, "auth.login_failed")
        raise _invalid()
    if passwords.needs_rehash(user.password_hash):
        user.password_hash = passwords.hash_password(password)
    rate_limit.clear(email, _ip())
    return user


def _fresh_session() -> None:
    """Nuova sessione a ogni cambio di stato: niente session fixation."""
    session.clear()
    g.pop("csrf_token", None)  # Flask-WTF tiene in `g` il token della sessione precedente


def _establish(user: User) -> str:
    _fresh_session()
    login_user(user)
    session.permanent = True
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
    _check_rate_limit(user.email)
    if not totp.verify_code(user, code):
        _fail(user.email, user.id, "auth.totp_failed")
        raise ServiceError("invalid_code", "Codice non valido", 401)
    rate_limit.clear(user.email, _ip())
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
    _check_rate_limit(user.email)
    if not passwords.verify_password(user.password_hash, current):
        _fail(user.email, user.id, "auth.password_change_failed")
        raise ServiceError("invalid_password", "La password attuale non è corretta", 401)
    users.set_password(user, new)
    audit.record("auth.password_changed", actor_id=user.id, entity="user", entity_id=user.id)
    token = _establish(user)
    db.session.commit()
    return token
