from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from flask import Flask

from app.services.passwords import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    PasswordPolicyError,
    hash_password,
    needs_rehash,
    validate_policy,
    verify_dummy,
    verify_password,
)


def test_policy_lengths() -> None:
    validate_policy("a" * MIN_PASSWORD_LENGTH)
    validate_policy("a" * MAX_PASSWORD_LENGTH)
    with pytest.raises(PasswordPolicyError, match=str(MIN_PASSWORD_LENGTH)):
        validate_policy("a" * (MIN_PASSWORD_LENGTH - 1))
    with pytest.raises(PasswordPolicyError, match=str(MAX_PASSWORD_LENGTH)):
        validate_policy("a" * (MAX_PASSWORD_LENGTH + 1))


def test_policy_rejects_only_spaces() -> None:
    with pytest.raises(PasswordPolicyError):
        validate_policy(" " * 20)


def test_hash_is_argon2id_and_verifies(app: Flask) -> None:
    with app.app_context():
        hashed = hash_password("Password-di-prova-123")
        assert hashed.startswith("$argon2id$")
        assert "Password-di-prova-123" not in hashed
        assert verify_password(hashed, "Password-di-prova-123")
        assert not verify_password(hashed, "Password-sbagliata-123")


def test_unicode_password_is_normalized(app: Flask) -> None:
    """ "è" composto (U+00E8) e "e" + accento (U+0065 U+0300) sono la stessa password."""
    composed = "Caffè-al-bar-123"
    decomposed = "Caffè-al-bar-123"
    with app.app_context():
        assert verify_password(hash_password(composed), decomposed)


def test_verify_handles_garbage_hash(app: Flask) -> None:
    with app.app_context():
        assert not verify_password("non-un-hash", "Password-di-prova-123")


def test_needs_rehash_when_parameters_change(app: Flask) -> None:
    old = PasswordHasher(time_cost=3, memory_cost=16, parallelism=1).hash("Password-di-prova-123")
    with app.app_context():
        assert needs_rehash(old)
        assert not needs_rehash(hash_password("Password-di-prova-123"))


def test_verify_dummy_never_succeeds(app: Flask) -> None:
    with app.app_context():
        assert verify_dummy("qualunque-password") is False
