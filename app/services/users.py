"""Gestione utenti: creazione, modifica, elenco, owner da CLI (D-31, D-32)."""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.user import EMAIL_MAX_LENGTH, Role, User
from app.services import audit
from app.services.errors import ServiceError, forbidden, not_found
from app.services.passwords import (
    PasswordPolicyError,
    hash_password,
    validate_policy,
    verify_password,
)
from app.services.permissions import (
    Permission,
    can_assign_role,
    can_manage,
    has_permission,
    permissions_for,
)

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
USER_NOT_FOUND = "Utente non trovato"


def normalize_email(raw: str) -> str:
    email = raw.strip().lower()
    if len(email) > EMAIL_MAX_LENGTH or not EMAIL_RE.fullmatch(email):
        raise ServiceError("invalid_email", "Indirizzo email non valido", 422)
    return email


def get_by_email(email: str) -> User | None:
    return db.session.execute(
        select(User).where(User.email == email.strip().lower())
    ).scalar_one_or_none()


def get_target(actor: User, user_id: int) -> User:
    """Utente gestibile da `actor`.

    404 sia se non esiste sia se non è gestibile: un admin non deve poter scoprire quali id
    appartengono a owner o admin (review sicurezza Fase 1). Su se stessi: 403 (si usa /me).
    """
    target = db.session.get(User, user_id)
    if target is not None and target.id == actor.id:
        raise forbidden()
    if target is None or not can_manage(actor, target):
        raise not_found(USER_NOT_FOUND)
    return target


def check_password(password: str) -> None:
    """Policy della password come errore di dominio (422 con messaggio in italiano)."""
    try:
        validate_policy(password)
    except PasswordPolicyError as exc:
        raise ServiceError("weak_password", str(exc), 422) from exc


def _email_taken() -> ServiceError:
    return ServiceError("email_taken", "Esiste già un utente con questa email", 409)


def _ensure_email_free(email: str) -> None:
    if get_by_email(email) is not None:
        raise _email_taken()


@contextmanager
def _unique_email_guard() -> Iterator[None]:
    """Con richieste parallele il controllo preventivo non basta: decide il vincolo UNIQUE
    del database, e l'errore diventa 409 invece di 500."""
    try:
        yield
    except IntegrityError as exc:
        db.session.rollback()
        raise _email_taken() from exc


def set_password(user: User, password: str) -> None:
    """Nuova password + nuova versione di sessione: le altre sessioni vengono chiuse (D-26)."""
    check_password(password)
    if verify_password(user.password_hash, password):
        raise ServiceError(
            "same_password", "La nuova password deve essere diversa da quella attuale", 422
        )
    user.password_hash = hash_password(password)
    user.session_version += 1


def _insert(email: str, password: str, role: str, can_publish: bool, actor_id: int | None) -> User:
    email = normalize_email(email)
    check_password(password)
    _ensure_email_free(email)
    user = User(
        email=email, password_hash=hash_password(password), role=role, can_publish=can_publish
    )
    with _unique_email_guard():
        db.session.add(user)
        db.session.flush()
        audit.record(
            "user.created",
            actor_id=actor_id,
            entity="user",
            entity_id=user.id,
            diff={"email": email, "role": role, "can_publish": can_publish},
        )
        db.session.commit()
    return user


def create_user(
    actor: User, *, email: str, password: str, role: str, can_publish: bool = False
) -> User:
    if not can_assign_role(actor, role):
        raise forbidden()
    return _insert(email, password, role, can_publish, actor.id)


def create_owner(email: str, password: str, *, additional: bool = False) -> User:
    """Solo da CLI (D-31): il ruolo owner non si assegna mai via API."""
    has_owner = db.session.execute(
        select(func.count()).select_from(User).where(User.role == Role.OWNER)
    ).scalar_one()
    if has_owner and not additional:
        raise ServiceError(
            "owner_exists", "Esiste già un owner: usa --additional per crearne un altro", 409
        )
    return _insert(email, password, Role.OWNER, True, None)


def _apply_role(actor: User, target: User, role: str, diff: dict[str, Any]) -> None:
    if role == target.role:
        return
    if not has_permission(actor, Permission.ROLES_MANAGE) or not can_assign_role(actor, role):
        raise forbidden()
    diff["role"] = [target.role, role]
    target.role = role
    target.session_version += 1  # i permessi cambiano: nuova sessione


def _apply_email(target: User, raw: str, diff: dict[str, Any]) -> None:
    email = normalize_email(raw)
    if email != target.email:
        _ensure_email_free(email)
        diff["email"] = [target.email, email]
        target.email = email


def update_user(actor: User, target: User, changes: Mapping[str, Any]) -> User:
    if not can_manage(actor, target):
        raise forbidden()
    diff: dict[str, Any] = {}
    if "role" in changes:
        _apply_role(actor, target, changes["role"], diff)
    if "email" in changes:
        _apply_email(target, changes["email"], diff)
    for flag in ("active", "can_publish"):
        if flag in changes and changes[flag] != getattr(target, flag):
            diff[flag] = [getattr(target, flag), changes[flag]]
            setattr(target, flag, changes[flag])
    if diff.get("active") == [True, False]:
        target.session_version += 1  # disattivazione: chiude subito le sue sessioni
    if "password" in changes:
        set_password(target, changes["password"])
        diff["credentials"] = "reset"
    if diff:  # niente righe vuote nel registro quando non cambia nulla
        audit.record(
            "user.updated", actor_id=actor.id, entity="user", entity_id=target.id, diff=diff
        )
    with _unique_email_guard():
        db.session.commit()
    return target


def list_users(actor: User, page: int, limit: int) -> tuple[list[User], int]:
    query = select(User)
    if actor.role != Role.OWNER:  # l'admin vede gli editor e se stesso
        query = query.where(or_(User.role == Role.EDITOR, User.id == actor.id))
    total = db.session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = db.session.execute(query.order_by(User.id).offset((page - 1) * limit).limit(limit))
    return list(rows.scalars()), total


def clear_totp(user: User) -> None:
    user.totp_secret_enc = None
    user.totp_last_counter = None


def reset_totp(actor: User, target: User) -> None:
    """Recupero del secondo fattore senza codici di recupero (D-29)."""
    if not can_manage(actor, target):
        raise forbidden()
    clear_totp(target)
    audit.record("totp.reset", actor_id=actor.id, entity="user", entity_id=target.id)
    db.session.commit()


def require_by_email(email: str) -> User:
    user = get_by_email(email)
    if user is None:
        raise not_found(USER_NOT_FOUND)
    return user


def serialize(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "active": user.active,
        "can_publish": user.can_publish,
        "totp_enabled": user.totp_enabled,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "tour_completed_at": (
            user.tour_completed_at.isoformat() if user.tour_completed_at else None
        ),
        "created_at": user.created_at.isoformat(),
    }


def serialize_me(user: User) -> dict[str, Any]:
    return {**serialize(user), "permissions": sorted(permissions_for(user))}
