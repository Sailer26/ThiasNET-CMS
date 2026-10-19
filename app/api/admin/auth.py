"""Route di autenticazione: sottili, la logica è in app/services/auth.py."""

from __future__ import annotations

from typing import Any

from flask import Response
from flask_wtf.csrf import generate_csrf

from app.api import ok
from app.api.admin import bp
from app.api.admin.decorators import current, public, require_permission
from app.api.validation import json_body
from app.services import auth, totp, users
from app.services.permissions import Permission

_TEXT = {"type": "string", "minLength": 1, "maxLength": 1024}
_CODE = {"type": "string", "pattern": "^[0-9]{6}$"}


def _schema(required: list[str], **properties: Any) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


LOGIN_SCHEMA = _schema(
    ["email", "password"], email={"type": "string", "maxLength": 320}, password=_TEXT
)
TOTP_LOGIN_SCHEMA = _schema(["code"], code=_CODE)
PASSWORD_SCHEMA = _schema(
    ["current_password", "new_password"], current_password=_TEXT, new_password=_TEXT
)
# Niente "secret": lo genera e lo conserva il server al setup (additionalProperties: false).
TOTP_ENABLE_SCHEMA = _schema(["code", "password"], code=_CODE, password=_TEXT)
TOTP_DISABLE_SCHEMA = _schema(["password", "code"], password=_TEXT, code=_CODE)


@bp.get("/auth/csrf")
@public
def csrf_token() -> Response:
    return ok({"csrf_token": generate_csrf()})


@bp.post("/auth/login")
@public
def login() -> Response:
    body = json_body(LOGIN_SCHEMA)
    user = auth.authenticate(body["email"], body["password"])
    if user.totp_enabled:
        return ok({"totp_required": True, "csrf_token": auth.begin_totp(user)})
    token = auth.start_session(user)
    return ok({"totp_required": False, "user": users.serialize(user), "csrf_token": token})


@bp.post("/auth/login/totp")
@public
def login_totp() -> Response:
    body = json_body(TOTP_LOGIN_SCHEMA)
    user = auth.complete_totp(body["code"])
    token = auth.start_session(user)
    return ok({"user": users.serialize(user), "csrf_token": token})


@bp.post("/auth/logout")
@require_permission(Permission.PROFILE)
def logout() -> Response:
    return ok({"csrf_token": auth.logout(current())})


@bp.post("/auth/logout-all")
@require_permission(Permission.PROFILE)
def logout_all() -> Response:
    return ok({"csrf_token": auth.logout_everywhere(current())})


@bp.get("/auth/me")
@require_permission(Permission.PROFILE)
def me() -> Response:
    return ok(users.serialize_me(current()))


@bp.post("/auth/me/tour")
@require_permission(Permission.PROFILE)
def finish_tour() -> Response:
    """Tour visto o saltato (D-133): riparte da solo solo finché non c'è la data."""
    return ok(users.serialize_me(users.finish_tour(current())))


@bp.post("/auth/password")
@require_permission(Permission.PROFILE)
def change_password() -> Response:
    body = json_body(PASSWORD_SCHEMA)
    token = auth.change_password(current(), body["current_password"], body["new_password"])
    return ok({"csrf_token": token})


@bp.post("/auth/totp/setup")
@require_permission(Permission.PROFILE)
def totp_setup() -> Response:
    secret, uri = totp.begin_setup(current())
    return ok({"secret": secret, "otpauth_uri": uri})


@bp.post("/auth/totp/enable")
@require_permission(Permission.PROFILE)
def totp_enable() -> Response:
    body = json_body(TOTP_ENABLE_SCHEMA)
    totp.enable(current(), code=body["code"], password=body["password"])
    return ok()


@bp.post("/auth/totp/disable")
@require_permission(Permission.PROFILE)
def totp_disable() -> Response:
    body = json_body(TOTP_DISABLE_SCHEMA)
    totp.disable(current(), password=body["password"], code=body["code"])
    return ok()
