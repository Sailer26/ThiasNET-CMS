"""Login, sessione, CSRF, rate limit e cambio password (API JSON per la SPA)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from argon2 import PasswordHasher
from flask import Flask
from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models.audit import AuditLog
from app.models.user import User
from app.services import auth, passwords, rate_limit
from tests.helpers import (
    API,
    LOGIN_URL,
    ME_URL,
    PASSWORD,
    adopt_csrf,
    api_client,
    error_code,
    login,
    make_user,
    session_cookie,
)

GENERIC_ERROR = "Email o password non corretti"


def _actions(app: Flask) -> list[str]:
    with app.app_context():
        return list(db.session.execute(select(AuditLog.action).order_by(AuditLog.id)).scalars())


# --- CSRF -----------------------------------------------------------------


def test_csrf_endpoint_returns_token(app: Flask) -> None:
    response = app.test_client().get(f"{API}/auth/csrf")
    body = response.get_json()
    assert response.status_code == 200
    assert body["success"] is True
    assert len(body["data"]["csrf_token"]) > 20


def test_post_without_csrf_is_rejected_with_403(app: Flask) -> None:
    make_user(app, "a@example.ch")
    response = app.test_client().post(
        LOGIN_URL, json={"email": "a@example.ch", "password": PASSWORD}
    )
    assert response.status_code == 403
    assert error_code(response) == "csrf"


def test_post_with_wrong_csrf_is_rejected(api: Any) -> None:
    api.environ_base["HTTP_X_CSRFTOKEN"] = "falso"
    response = api.post(LOGIN_URL, json={"email": "a@example.ch", "password": PASSWORD})
    assert response.status_code == 403


# --- Login ----------------------------------------------------------------


def test_login_success_returns_user_and_new_csrf(app: Flask, api: Any) -> None:
    user = make_user(app, "admin@example.ch", "admin")
    response = login(api, "  ADMIN@example.ch ")
    body = response.get_json()
    assert response.status_code == 200
    assert body["data"]["user"]["email"] == "admin@example.ch"
    assert body["data"]["user"]["role"] == "admin"
    assert "password_hash" not in body["data"]["user"]
    assert body["data"]["csrf_token"]
    me = api.get(ME_URL).get_json()["data"]
    assert me["id"] == user.id
    assert "users.manage" in me["permissions"]
    assert _actions(app) == ["auth.login"]


def test_login_wrong_password_is_generic_401(app: Flask, api: Any) -> None:
    make_user(app, "a@example.ch")
    response = login(api, "a@example.ch", "Password-sbagliata-1")
    assert response.status_code == 401
    assert response.get_json()["error"]["message"] == GENERIC_ERROR
    assert _actions(app) == ["auth.login_failed"]


def test_unknown_email_same_response_and_dummy_verify(
    app: Flask, api: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    real = passwords.verify_dummy

    def spy(password: str) -> bool:
        calls.append(password)
        return real(password)

    monkeypatch.setattr(passwords, "verify_dummy", spy)
    response = login(api, "nessuno@example.ch", "Password-qualunque-1")
    assert response.status_code == 401
    assert response.get_json()["error"]["message"] == GENERIC_ERROR
    assert calls == ["Password-qualunque-1"]
    with app.app_context():
        entry = db.session.execute(select(AuditLog)).scalar_one()
        assert entry.user_id is None
        assert "nessuno" not in str(entry.diff_json)


def test_inactive_user_cannot_login(app: Flask, api: Any) -> None:
    make_user(app, "a@example.ch", active=False)
    assert login(api, "a@example.ch").status_code == 401


def test_invalid_body_is_422(api: Any) -> None:
    assert api.post(LOGIN_URL, json={"email": "a@example.ch"}).status_code == 422
    assert api.post(LOGIN_URL, data="non json").status_code == 422


def test_me_requires_login_json_401(api: Any) -> None:
    response = api.get(ME_URL)
    assert response.status_code == 401
    assert response.is_json
    assert error_code(response) == "unauthorized"


def test_unknown_api_route_is_json_404(api: Any) -> None:
    response = api.get(f"{API}/non-esiste")
    assert response.status_code == 404
    assert response.is_json


# --- Sessione -------------------------------------------------------------


def test_session_is_regenerated_on_login(app: Flask, api: Any) -> None:
    make_user(app, "a@example.ch")
    before = session_cookie(api)
    assert before is not None
    login(api, "a@example.ch")
    assert session_cookie(api) != before


def test_old_session_cookie_is_useless_after_logout(app: Flask, api: Any) -> None:
    make_user(app, "a@example.ch")
    login(api, "a@example.ch")
    assert api.post(f"{API}/auth/logout").status_code == 200
    assert api.get(ME_URL).status_code == 401
    assert "auth.logout" in _actions(app)


def test_session_is_permanent_12h(app: Flask, api: Any) -> None:
    make_user(app, "a@example.ch")
    login(api, "a@example.ch")
    cookie = api.get_cookie("session")
    assert cookie is not None
    assert cookie.expires is not None
    assert cookie.http_only


def test_password_change_invalidates_other_sessions(app: Flask) -> None:
    make_user(app, "a@example.ch")
    laptop, tablet = api_client(app), api_client(app)
    login(laptop, "a@example.ch")
    login(tablet, "a@example.ch")
    response = laptop.post(
        f"{API}/auth/password",
        json={"current_password": PASSWORD, "new_password": "Nuova-password-sicura-1"},
    )
    assert response.status_code == 200
    adopt_csrf(laptop, response)
    assert laptop.get(ME_URL).status_code == 200
    assert tablet.get(ME_URL).status_code == 401
    assert login(api_client(app), "a@example.ch", "Nuova-password-sicura-1").status_code == 200
    assert "auth.password_changed" in _actions(app)


def test_password_change_wrong_current_is_401(app: Flask, api: Any) -> None:
    make_user(app, "a@example.ch")
    login(api, "a@example.ch")
    response = api.post(
        f"{API}/auth/password",
        json={"current_password": "Sbagliata-123456", "new_password": "Nuova-password-sicura-1"},
    )
    assert response.status_code == 401


def test_password_change_weak_is_422(app: Flask, api: Any) -> None:
    make_user(app, "a@example.ch")
    login(api, "a@example.ch")
    response = api.post(
        f"{API}/auth/password", json={"current_password": PASSWORD, "new_password": "corta"}
    )
    assert response.status_code == 422
    assert "12" in response.get_json()["error"]["message"]


def test_password_change_to_same_password_is_422(app: Flask, api: Any) -> None:
    make_user(app, "a@example.ch")
    login(api, "a@example.ch")
    response = api.post(
        f"{API}/auth/password", json={"current_password": PASSWORD, "new_password": PASSWORD}
    )
    assert response.status_code == 422
    assert error_code(response) == "same_password"


def test_password_change_to_common_password_is_422(app: Flask, api: Any) -> None:
    make_user(app, "a@example.ch")
    login(api, "a@example.ch")
    response = api.post(
        f"{API}/auth/password",
        json={"current_password": PASSWORD, "new_password": "Password1234"},
    )
    assert response.status_code == 422
    assert error_code(response) == "weak_password"


def test_logout_all_invalidates_every_session(app: Flask) -> None:
    make_user(app, "a@example.ch")
    laptop, tablet = api_client(app), api_client(app)
    login(laptop, "a@example.ch")
    login(tablet, "a@example.ch")
    assert laptop.post(f"{API}/auth/logout-all").status_code == 200
    assert laptop.get(ME_URL).status_code == 401
    assert tablet.get(ME_URL).status_code == 401


def test_password_is_rehashed_when_parameters_change(app: Flask, api: Any) -> None:
    user = make_user(app, "a@example.ch")
    old_hash = PasswordHasher(time_cost=2, memory_cost=64, parallelism=1).hash(PASSWORD)
    with app.app_context():
        db.session.get_one(User, user.id).password_hash = old_hash
        db.session.commit()
    assert login(api, "a@example.ch").status_code == 200
    with app.app_context():
        new_hash = db.session.get_one(User, user.id).password_hash
    assert new_hash != old_hash
    assert new_hash.startswith("$argon2id$")


def test_session_has_absolute_limit(app: Flask, api: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """La sessione si rinnova usando il pannello, ma non oltre un tetto assoluto (D-27)."""
    make_user(app, "a@example.ch")
    login(api, "a@example.ch")
    assert api.get(ME_URL).status_code == 200
    later = datetime.now(UTC) + auth.ABSOLUTE_SESSION_LIMIT + timedelta(minutes=1)
    monkeypatch.setattr(auth, "_now", lambda: later)
    assert api.get(ME_URL).status_code == 401


def test_api_responses_are_hardened(api: Any) -> None:
    response = api.get(ME_URL)
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


# --- Rate limit -----------------------------------------------------------


def test_sixth_attempt_is_429_with_retry_after(app: Flask, api: Any) -> None:
    make_user(app, "a@example.ch")
    for _ in range(rate_limit.MAX_PER_EMAIL_IP):
        assert login(api, "a@example.ch", "Sbagliata-123456").status_code == 401
    response = login(api, "a@example.ch")  # anche con la password giusta
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
    assert error_code(response) == "rate_limited"


def test_rate_limit_also_for_unknown_email(api: Any) -> None:
    for _ in range(rate_limit.MAX_PER_EMAIL_IP):
        login(api, "nessuno@example.ch", "Sbagliata-123456")
    assert login(api, "nessuno@example.ch", "Sbagliata-123456").status_code == 429


def test_other_ip_is_not_blocked(app: Flask) -> None:
    make_user(app, "a@example.ch")
    attacker = api_client(app, ip="198.51.100.1")
    for _ in range(rate_limit.MAX_PER_EMAIL_IP):
        login(attacker, "a@example.ch", "Sbagliata-123456")
    assert login(attacker, "a@example.ch").status_code == 429
    assert login(api_client(app, ip="203.0.113.99"), "a@example.ch").status_code == 200


def test_success_resets_counter(app: Flask, api: Any) -> None:
    make_user(app, "a@example.ch")
    for _ in range(rate_limit.MAX_PER_EMAIL_IP - 1):
        login(api, "a@example.ch", "Sbagliata-123456")
    assert login(api, "a@example.ch").status_code == 200
    adopt_csrf(api, api.post(f"{API}/auth/logout"))
    for _ in range(rate_limit.MAX_PER_EMAIL_IP - 1):
        assert login(api, "a@example.ch", "Sbagliata-123456").status_code == 401


# --- ProxyFix -------------------------------------------------------------


def _proxy_app(count: int) -> Flask:
    app = create_app("testing", overrides={"TRUSTED_PROXY_COUNT": count})
    with app.app_context():
        db.create_all()
    return app


def test_forwarded_for_is_ignored_without_trusted_proxy() -> None:
    app = _proxy_app(0)
    client = api_client(app, ip="10.0.0.1")
    for i in range(rate_limit.MAX_PER_EMAIL_IP):
        client.environ_base["HTTP_X_FORWARDED_FOR"] = f"198.51.100.{i}"
        login(client, "a@example.ch", "Sbagliata-123456")
    client.environ_base["HTTP_X_FORWARDED_FOR"] = "198.51.100.200"
    assert login(client, "a@example.ch", "Sbagliata-123456").status_code == 429


def test_forwarded_for_is_used_behind_trusted_proxy() -> None:
    app = _proxy_app(1)
    client = api_client(app, ip="10.0.0.1")
    client.environ_base["HTTP_X_FORWARDED_FOR"] = "198.51.100.1"
    for _ in range(rate_limit.MAX_PER_EMAIL_IP):
        login(client, "a@example.ch", "Sbagliata-123456")
    client.environ_base["HTTP_X_FORWARDED_FOR"] = "198.51.100.2"
    assert login(client, "a@example.ch", "Sbagliata-123456").status_code == 401
