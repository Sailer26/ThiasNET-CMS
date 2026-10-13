"""Secondo fattore TOTP opzionale (D-28, D-29)."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import pyotp
import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.extensions import db
from app.models.user import User
from app.services import auth, rate_limit
from tests.helpers import (
    API,
    ME_URL,
    PASSWORD,
    TOTP_LOGIN_URL,
    adopt_csrf,
    api_client,
    error_code,
    login,
    make_user,
)

TOTP = f"{API}/auth/totp"


def _enable(client: FlaskClient) -> str:
    secret: str = client.post(f"{TOTP}/setup").get_json()["data"]["secret"]
    response = client.post(
        f"{TOTP}/enable",
        json={"secret": secret, "code": pyotp.TOTP(secret).now(), "password": PASSWORD},
    )
    assert response.status_code == 200, response.get_json()
    return secret


def _next_code(secret: str) -> str:
    """Codice del passo successivo: diverso da quello già usato all'attivazione."""
    return pyotp.TOTP(secret).at(int(time.time()) + 30)


@pytest.fixture
def totp_user(app: Flask) -> tuple[FlaskClient, str]:
    make_user(app, "a@example.ch", "admin")
    client = api_client(app)
    login(client, "a@example.ch")
    return client, _enable(client)


def test_setup_returns_secret_and_uri_without_saving(app: Flask) -> None:
    user = make_user(app, "a@example.ch")
    client = api_client(app)
    login(client, "a@example.ch")
    data = client.post(f"{TOTP}/setup").get_json()["data"]
    assert data["otpauth_uri"].startswith("otpauth://totp/")
    assert "ThiasNET" in data["otpauth_uri"]
    with app.app_context():
        assert db.session.get_one(User, user.id).totp_secret_enc is None


def test_enable_requires_correct_code_and_password(app: Flask) -> None:
    make_user(app, "a@example.ch")
    client = api_client(app)
    login(client, "a@example.ch")
    secret = client.post(f"{TOTP}/setup").get_json()["data"]["secret"]
    wrong_code = client.post(
        f"{TOTP}/enable", json={"secret": secret, "code": "000000", "password": PASSWORD}
    )
    assert wrong_code.status_code == 401
    wrong_pw = client.post(
        f"{TOTP}/enable",
        json={"secret": secret, "code": pyotp.TOTP(secret).now(), "password": "Sbagliata-12345"},
    )
    assert wrong_pw.status_code == 401


def test_secret_is_encrypted_in_database(app: Flask, totp_user: Any) -> None:
    client, secret = totp_user
    with app.app_context():
        user = db.session.query(User).one()
        assert user.totp_secret_enc
        assert secret not in user.totp_secret_enc
    assert client.get(ME_URL).get_json()["data"]["totp_enabled"] is True


def test_enable_twice_is_409(totp_user: Any) -> None:
    client, _ = totp_user
    secret = client.post(f"{TOTP}/setup").get_json()["data"]["secret"]
    response = client.post(
        f"{TOTP}/enable",
        json={"secret": secret, "code": pyotp.TOTP(secret).now(), "password": PASSWORD},
    )
    assert response.status_code == 409


def test_login_with_totp_is_two_step(app: Flask, totp_user: Any) -> None:
    _, secret = totp_user
    client = api_client(app)
    first = login(client, "a@example.ch")
    assert first.status_code == 200
    assert first.get_json()["data"]["totp_required"] is True
    assert client.get(ME_URL).status_code == 401
    second = client.post(TOTP_LOGIN_URL, json={"code": _next_code(secret)})
    assert second.status_code == 200
    adopt_csrf(client, second)
    assert client.get(ME_URL).status_code == 200


def test_totp_code_cannot_be_replayed(app: Flask, totp_user: Any) -> None:
    _, secret = totp_user
    code = _next_code(secret)
    first = api_client(app)
    login(first, "a@example.ch")
    assert first.post(TOTP_LOGIN_URL, json={"code": code}).status_code == 200
    second = api_client(app, ip="203.0.113.20")
    login(second, "a@example.ch")
    assert second.post(TOTP_LOGIN_URL, json={"code": code}).status_code == 401


def test_totp_step_without_password_step_is_401(api: Any) -> None:
    response = api.post(TOTP_LOGIN_URL, json={"code": "123456"})
    assert response.status_code == 401


def test_pending_totp_expires(app: Flask, totp_user: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _, secret = totp_user
    client = api_client(app)
    login(client, "a@example.ch")
    later = datetime.now(UTC) + auth.PENDING_TOTP_TTL + timedelta(seconds=1)
    monkeypatch.setattr(auth, "_now", lambda: later)
    response = client.post(TOTP_LOGIN_URL, json={"code": _next_code(secret)})
    assert response.status_code == 410
    assert error_code(response) == "totp_expired"


def test_wrong_totp_codes_count_in_rate_limit(app: Flask, totp_user: Any) -> None:
    client = api_client(app)
    login(client, "a@example.ch")
    for _ in range(rate_limit.MAX_PER_EMAIL_IP):
        assert client.post(TOTP_LOGIN_URL, json={"code": "000000"}).status_code == 401
    assert client.post(TOTP_LOGIN_URL, json={"code": "000000"}).status_code == 429


def test_disable_requires_password_and_code(totp_user: Any) -> None:
    client, secret = totp_user
    bad = client.post(f"{TOTP}/disable", json={"password": PASSWORD, "code": "000000"})
    assert bad.status_code == 401
    ok = client.post(f"{TOTP}/disable", json={"password": PASSWORD, "code": _next_code(secret)})
    assert ok.status_code == 200
    assert client.get(ME_URL).get_json()["data"]["totp_enabled"] is False
