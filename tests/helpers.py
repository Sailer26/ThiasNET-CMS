"""Aiuti per i test delle API admin (sessione + CSRF come farà la SPA)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask import Flask
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

from app.extensions import db
from app.models.user import User
from app.services.passwords import hash_password

PASSWORD = "Password-di-prova-123"
CSRF_HEADER = "HTTP_X_CSRFTOKEN"
API = "/api/admin"
CSRF_URL = f"{API}/auth/csrf"
LOGIN_URL = f"{API}/auth/login"
TOTP_LOGIN_URL = f"{API}/auth/login/totp"
ME_URL = f"{API}/auth/me"


@dataclass(frozen=True)
class UserRef:
    id: int
    email: str
    role: str
    password: str = PASSWORD


def make_user(
    app: Flask,
    email: str,
    role: str = "editor",
    *,
    password: str = PASSWORD,
    active: bool = True,
    can_publish: bool = False,
) -> UserRef:
    with app.app_context():
        user = User(
            email=email,
            password_hash=hash_password(password),
            role=role,
            active=active,
            can_publish=can_publish,
        )
        db.session.add(user)
        db.session.commit()
        return UserRef(id=user.id, email=email, role=role, password=password)


def refresh_csrf(client: FlaskClient) -> str:
    token: str = client.get(CSRF_URL).get_json()["data"]["csrf_token"]
    client.environ_base[CSRF_HEADER] = token
    return token


def api_client(app: Flask, ip: str = "203.0.113.10") -> FlaskClient:
    client = app.test_client()
    client.environ_base["REMOTE_ADDR"] = ip
    refresh_csrf(client)
    return client


def adopt_csrf(client: FlaskClient, response: TestResponse) -> None:
    """Dopo login/cambio password il server ruota la sessione e restituisce un nuovo token."""
    body = response.get_json(silent=True) or {}
    token = (body.get("data") or {}).get("csrf_token")
    if token:
        client.environ_base[CSRF_HEADER] = token


def login(client: FlaskClient, email: str, password: str = PASSWORD) -> TestResponse:
    response = client.post(LOGIN_URL, json={"email": email, "password": password})
    adopt_csrf(client, response)
    return response


def error_code(response: TestResponse) -> Any:
    return (response.get_json() or {}).get("error", {}).get("code")


def session_cookie(client: FlaskClient) -> str | None:
    cookie = client.get_cookie("session")
    return cookie.value if cookie else None
