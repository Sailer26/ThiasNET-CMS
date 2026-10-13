"""Controllo d'accesso delle route admin (D-33).

Ogni route `/api/admin/*` usa `@require_permission(...)` oppure `@public`: un meta-test
fallisce se una route non dichiara nulla.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, cast

from flask_login import current_user

from app.api import unauthorized
from app.models.user import User
from app.services.errors import forbidden
from app.services.permissions import Permission, has_permission

PUBLIC_ATTR = "__public_endpoint__"
REQUIRED_PERMISSION_ATTR = "__required_permission__"


def public[View: Callable[..., Any]](view: View) -> View:
    """Route accessibile senza login (csrf, login). Il CSRF resta comunque attivo."""
    setattr(view, PUBLIC_ATTR, True)
    return view


def require_permission[View: Callable[..., Any]](
    permission: Permission,
) -> Callable[[View], View]:
    def decorator(view: View) -> View:
        @wraps(view)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not current_user.is_authenticated:
                return unauthorized()
            if not has_permission(current(), permission):
                raise forbidden()
            return view(*args, **kwargs)

        setattr(wrapper, REQUIRED_PERMISSION_ATTR, permission)
        return cast(View, wrapper)

    return decorator


def current() -> User:
    """Utente loggato con il tipo giusto (current_user è un proxy)."""
    return cast(User, current_user._get_current_object())
