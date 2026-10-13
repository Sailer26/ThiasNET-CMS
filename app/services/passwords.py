"""Password: policy e hash Argon2id con rehash automatico (D-25)."""

from __future__ import annotations

from functools import cache

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from flask import current_app

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128  # limite superiore: evita di far calcolare hash su testi enormi
_DUMMY_PASSWORD = "thiasnet-password-fittizia-per-tempi-costanti"  # noqa: S105


class PasswordPolicyError(ValueError):
    """Password non conforme: il messaggio è in italiano e mostrabile all'utente."""


def validate_policy(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(f"La password deve avere almeno {MIN_PASSWORD_LENGTH} caratteri")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"La password può avere al massimo {MAX_PASSWORD_LENGTH} caratteri"
        )
    if not password.strip():
        raise PasswordPolicyError("La password non può essere fatta solo di spazi")


@cache
def _hasher_for(time_cost: int, memory_cost: int, parallelism: int) -> PasswordHasher:
    return PasswordHasher(
        time_cost=time_cost, memory_cost=memory_cost, parallelism=parallelism, type=Type.ID
    )


def _params() -> tuple[int, int, int]:
    config = current_app.config
    return (
        int(config["ARGON2_TIME_COST"]),
        int(config["ARGON2_MEMORY_COST"]),
        int(config["ARGON2_PARALLELISM"]),
    )


def _hasher() -> PasswordHasher:
    return _hasher_for(*_params())


def hash_password(password: str) -> str:
    return _hasher().hash(password)


def verify_password(hashed: str, password: str) -> bool:
    try:
        return _hasher().verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    try:
        return _hasher().check_needs_rehash(hashed)
    except InvalidHashError:
        return True


@cache
def _dummy_hash(time_cost: int, memory_cost: int, parallelism: int) -> str:
    return _hasher_for(time_cost, memory_cost, parallelism).hash(_DUMMY_PASSWORD)


def verify_dummy(password: str) -> bool:
    """Stesso costo di una verifica vera per email inesistenti: i tempi di risposta non
    rivelano quali email sono registrate. Restituisce sempre False."""
    verify_password(_dummy_hash(*_params()), password)
    return False
