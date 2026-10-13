"""Chiavi derivate da SECRET_KEY (HKDF): cifratura dei segreti TOTP e hash con chiave.

Ogni uso ha la sua chiave (parametro `info`), così una chiave non serve per un altro scopo.
Ruotare SECRET_KEY rende illeggibili i segreti TOTP: usare `flask disable-totp` (D-28).
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from flask import current_app

KEY_LENGTH = 32
TOTP_KEY_INFO = b"thiasnet-totp-v1"


def _derive(info: bytes) -> bytes:
    secret = str(current_app.config["SECRET_KEY"]).encode()
    return HKDF(algorithm=hashes.SHA256(), length=KEY_LENGTH, salt=None, info=info).derive(secret)


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_derive(TOTP_KEY_INFO)))


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str:
    """Solleva cryptography.fernet.InvalidToken se la chiave è cambiata o il dato è alterato."""
    return _fernet().decrypt(token.encode()).decode()


def keyed_hash(value: str, purpose: str) -> str:
    """HMAC-SHA256 esadecimale (64 caratteri) con una chiave dedicata a `purpose`."""
    key = _derive(f"thiasnet-hmac-{purpose}".encode())
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()


def hash_ip(ip: str | None) -> str | None:
    """Impronta dell'IP per l'audit (D-30): confrontabile, ma l'IP non è ricostruibile."""
    return keyed_hash(ip, "ip-v1") if ip else None
