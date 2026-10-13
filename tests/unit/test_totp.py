"""Anti-replay atomico del codice TOTP (review Fase 1)."""

from __future__ import annotations

from datetime import UTC, datetime

import pyotp
from flask import Flask
from sqlalchemy import update

from app.extensions import db
from app.models.user import User
from app.services import totp
from app.services.crypto import encrypt_secret
from tests.helpers import make_user


def test_same_code_is_accepted_once_even_with_stale_object(app: Flask) -> None:
    """Due richieste parallele con lo stesso codice: solo una passa, anche se la seconda
    ha letto l'utente prima che la prima salvasse il contatore."""
    ref = make_user(app, "a@example.ch")
    secret = pyotp.random_base32()
    code = pyotp.TOTP(secret).now()
    counter = pyotp.TOTP(secret).timecode(datetime.now(UTC))
    with app.app_context():
        db.session.get_one(User, ref.id).totp_secret_enc = encrypt_secret(secret)
        db.session.commit()
        stale = db.session.get_one(User, ref.id)
        # un'altra richiesta ha già consumato il codice, aggiornando solo il database
        db.session.execute(
            update(User)
            .where(User.id == ref.id)
            .values(totp_last_counter=counter + 1)
            .execution_options(synchronize_session=False)
        )
        assert stale.totp_last_counter is None  # l'oggetto in memoria è vecchio
        assert totp.verify_code(stale, code) is False


def test_valid_code_is_accepted_and_counter_saved(app: Flask) -> None:
    ref = make_user(app, "a@example.ch")
    secret = pyotp.random_base32()
    with app.app_context():
        user = db.session.get_one(User, ref.id)
        user.totp_secret_enc = encrypt_secret(secret)
        db.session.commit()
        assert totp.verify_code(user, pyotp.TOTP(secret).now()) is True
        db.session.commit()
        assert db.session.get_one(User, ref.id).totp_last_counter is not None
