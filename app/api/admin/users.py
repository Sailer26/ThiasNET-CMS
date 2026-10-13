"""Route di gestione utenti (permessi in app/services/permissions.py)."""

from __future__ import annotations

from typing import Any

from flask import Response

from app.api import ok
from app.api.admin import bp
from app.api.admin.decorators import current, require_permission
from app.api.validation import json_body, page_meta, pagination
from app.services import users
from app.services.permissions import Permission

_ROLE = {"enum": ["admin", "editor"]}  # owner mai via API (D-31)
_EMAIL = {"type": "string", "maxLength": 320}
_PASSWORD = {"type": "string", "minLength": 1, "maxLength": 1024}

CREATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["email", "password", "role"],
    "properties": {
        "email": _EMAIL,
        "password": _PASSWORD,
        "role": _ROLE,
        "can_publish": {"type": "boolean"},
    },
}
UPDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "minProperties": 1,
    "properties": {
        "email": _EMAIL,
        "password": _PASSWORD,
        "role": _ROLE,
        "active": {"type": "boolean"},
        "can_publish": {"type": "boolean"},
    },
}


@bp.get("/users")
@require_permission(Permission.USERS_VIEW)
def list_users() -> Response:
    page, limit = pagination()
    items, total = users.list_users(current(), page, limit)
    return ok([users.serialize(u) for u in items], meta=page_meta(page, limit, total))


@bp.post("/users")
@require_permission(Permission.USERS_MANAGE)
def create_user() -> Response:
    body = json_body(CREATE_SCHEMA)
    user = users.create_user(
        current(),
        email=body["email"],
        password=body["password"],
        role=body["role"],
        can_publish=body.get("can_publish", False),
    )
    return ok(users.serialize(user), status=201)


@bp.get("/users/<int:user_id>")
@require_permission(Permission.USERS_MANAGE)
def get_user(user_id: int) -> Response:
    return ok(users.serialize(users.get_target(current(), user_id)))


@bp.patch("/users/<int:user_id>")
@require_permission(Permission.USERS_MANAGE)
def update_user(user_id: int) -> Response:
    body = json_body(UPDATE_SCHEMA)
    target = users.get_target(current(), user_id)
    return ok(users.serialize(users.update_user(current(), target, body)))


@bp.post("/users/<int:user_id>/totp/reset")
@require_permission(Permission.USERS_MANAGE)
def reset_totp(user_id: int) -> Response:
    users.reset_totp(current(), users.get_target(current(), user_id))
    return ok()
