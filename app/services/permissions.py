"""Permessi dei ruoli: l'unico punto in cui si decide chi può fare cosa (D-33)."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from app.models.user import Role, User


class Permission(StrEnum):
    PROFILE = "profile"  # il proprio account: password, TOTP, logout
    CONTENT_EDIT = "content.edit"
    PUBLISH = "content.publish"
    USERS_VIEW = "users.view"
    USERS_MANAGE = "users.manage"
    ROLES_MANAGE = "roles.manage"
    AUDIT_VIEW = "audit.view"


ROLE_PERMISSIONS: Mapping[str, frozenset[Permission]] = MappingProxyType(
    {
        Role.OWNER: frozenset(Permission),
        Role.ADMIN: frozenset(
            {
                Permission.PROFILE,
                Permission.CONTENT_EDIT,
                Permission.PUBLISH,
                Permission.USERS_VIEW,
                Permission.USERS_MANAGE,
            }
        ),
        Role.EDITOR: frozenset({Permission.PROFILE, Permission.CONTENT_EDIT}),
    }
)

# Ruoli che ciascun ruolo può creare e gestire. Nessuno gestisce gli owner via API (D-31).
MANAGEABLE_ROLES: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        Role.OWNER: frozenset({Role.ADMIN, Role.EDITOR}),
        Role.ADMIN: frozenset({Role.EDITOR}),
        Role.EDITOR: frozenset(),
    }
)


def permissions_for(user: User) -> frozenset[Permission]:
    granted = ROLE_PERMISSIONS.get(user.role, frozenset())
    if user.role == Role.EDITOR and user.can_publish:  # D-15
        granted = granted | {Permission.PUBLISH}
    return granted


def has_permission(user: User, permission: Permission) -> bool:
    return permission in permissions_for(user)


def can_assign_role(actor: User, role: str) -> bool:
    return role in MANAGEABLE_ROLES.get(actor.role, frozenset())


def can_manage(actor: User, target: User) -> bool:
    """Nessuno gestisce se stesso da qui (si usa /auth/me): evita auto-disattivazioni."""
    return actor.id != target.id and can_assign_role(actor, target.role)
