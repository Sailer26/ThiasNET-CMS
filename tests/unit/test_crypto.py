from __future__ import annotations

import pytest
from cryptography.fernet import InvalidToken
from flask import Flask

from app.services.crypto import decrypt_secret, encrypt_secret, hash_ip, keyed_hash


def test_encrypt_roundtrip_and_not_plaintext(app: Flask) -> None:
    with app.app_context():
        token = encrypt_secret("JBSWY3DPEHPK3PXP")
        assert "JBSWY3DPEHPK3PXP" not in token
        assert decrypt_secret(token) == "JBSWY3DPEHPK3PXP"


def test_other_secret_key_cannot_decrypt(app: Flask) -> None:
    with app.app_context():
        token = encrypt_secret("JBSWY3DPEHPK3PXP")
    other = Flask(__name__)
    other.config["SECRET_KEY"] = "un-altra-chiave-segreta-molto-lunga-123"
    with other.app_context(), pytest.raises(InvalidToken):
        decrypt_secret(token)


def test_keyed_hash_is_stable_and_purpose_separated(app: Flask) -> None:
    with app.app_context():
        assert keyed_hash("x", "a") == keyed_hash("x", "a")
        assert keyed_hash("x", "a") != keyed_hash("x", "b")
        assert len(keyed_hash("x", "a")) == 64


def test_hash_ip(app: Flask) -> None:
    with app.app_context():
        digest = hash_ip("203.0.113.10")
        assert digest is not None
        assert "203.0.113.10" not in digest
        assert hash_ip(None) is None
