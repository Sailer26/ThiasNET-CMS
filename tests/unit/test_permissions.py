"""Matrice completa dei permessi (D-15, D-33, D-48): nessun valore nuovo in Fase 2."""

from __future__ import annotations

import pytest

from app.models.user import User
from app.services.permissions import Permission, has_permission

P = Permission
MATRIX: dict[tuple[str, bool], set[Permission]] = {
    ("owner", False): set(Permission),
    ("admin", False): {P.PROFILE, P.CONTENT_EDIT, P.PUBLISH, P.USERS_VIEW, P.USERS_MANAGE},
    ("editor", False): {P.PROFILE, P.CONTENT_EDIT},
    ("editor", True): {P.PROFILE, P.CONTENT_EDIT, P.PUBLISH},
    # can_publish non dà nulla in più a chi pubblica già
    ("admin", True): {P.PROFILE, P.CONTENT_EDIT, P.PUBLISH, P.USERS_VIEW, P.USERS_MANAGE},
}


@pytest.mark.parametrize(("role", "can_publish"), sorted(MATRIX))
@pytest.mark.parametrize("permission", sorted(Permission))
def test_permission_matrix(role: str, can_publish: bool, permission: Permission) -> None:
    user = User(email="x@example.ch", password_hash="x", role=role, can_publish=can_publish)
    assert has_permission(user, permission) is (permission in MATRIX[(role, can_publish)])


def test_unknown_role_has_no_permissions() -> None:
    user = User(email="x@example.ch", password_hash="x", role="guest", can_publish=True)
    assert not any(has_permission(user, p) for p in Permission)


def test_permission_values_are_stable() -> None:
    assert {p.value for p in Permission} == {
        "profile",
        "content.edit",
        "content.publish",
        "users.view",
        "users.manage",
        "roles.manage",
        "audit.view",
    }
