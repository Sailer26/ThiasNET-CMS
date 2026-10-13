"""Meta-test (D-33): ogni route /api/admin dichiara un permesso oppure è pubblica di proposito."""

from __future__ import annotations

from flask import Flask

from app.api.admin.decorators import PUBLIC_ATTR, REQUIRED_PERMISSION_ATTR

EXPECTED_PUBLIC = {
    "/api/admin/auth/csrf",
    "/api/admin/auth/login",
    "/api/admin/auth/login/totp",
}


def test_every_admin_route_declares_access(app: Flask) -> None:
    public, undeclared = set(), []
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/api/admin"):
            continue
        view = app.view_functions[rule.endpoint]
        if getattr(view, PUBLIC_ATTR, False):
            public.add(rule.rule)
        elif getattr(view, REQUIRED_PERMISSION_ATTR, None) is None:
            undeclared.append(rule.rule)
    assert not undeclared, f"Route senza permesso dichiarato: {undeclared}"
    assert public == EXPECTED_PUBLIC
