"""Lettura e salvataggio delle impostazioni (D-143): blocco ottimistico, registro, versioni,
cache del sito. Le letture si tengono per la durata del contesto (una richiesta)."""

from __future__ import annotations

from typing import Any

from flask import current_app, g
from sqlalchemy import select, update

from app.extensions import db
from app.models.settings import SettingsRow
from app.models.types import utcnow
from app.models.user import User
from app.services import audit, entity_revisions, page_cache
from app.services.content import invalid
from app.services.errors import ServiceError, version_conflict
from app.services.permissions import Permission, require
from app.services.settings_fields import SITE_FIELDS, Field, lenient, schema, theme_fields, validate
from app.services.sql import rows_affected
from app.services.theme import Theme, active_theme

SCOPES = ("site", "appearance")
CACHE_KEY = "_thiasnet_settings"


def fields(scope: str, theme: Theme) -> tuple[Field, ...]:
    return SITE_FIELDS if scope == "site" else theme_fields(theme)


def _rows() -> dict[str, SettingsRow]:
    cached: dict[str, SettingsRow] | None = g.get(CACHE_KEY)
    if cached is None:
        cached = {row.scope: row for row in db.session.execute(select(SettingsRow)).scalars()}
        setattr(g, CACHE_KEY, cached)
    return cached


def forget() -> None:
    g.pop(CACHE_KEY, None)


def stored(scope: str) -> dict[str, Any]:
    row = _rows().get(scope)
    return dict(row.values_json or {}) if row is not None else {}


def defaults(scope: str, theme: Theme) -> dict[str, Any]:
    """D-57: finché nessuno salva, nome e destinatario vengono dalla configurazione."""
    if scope == "site":
        config = current_app.config
        found = {
            "name": config.get("SITE_NAME"),
            "contact_recipient": config.get("CONTACT_RECIPIENT"),
        }
    else:
        found = {key: spec.default for key, spec in theme.settings.items()}
    return {key: value for key, value in found.items() if value is not None}


def effective(scope: str, theme: Theme) -> dict[str, Any]:
    return {**defaults(scope, theme), **lenient(fields(scope, theme), stored(scope))}


def section(scope: str, theme: Theme) -> dict[str, Any]:
    row = _rows().get(scope)
    return {
        "schema": schema(fields(scope, theme)),
        "values": effective(scope, theme),
        "version": row.version if row is not None else 0,
    }


def _conflict(row: SettingsRow | None) -> ServiceError:
    if row is None:
        return version_conflict(0, None, None)
    return version_conflict(row.version, row.updated_by, row.updated_at)


def _write(scope: str, version: int, values: dict[str, Any], actor: User) -> None:
    row = _rows().get(scope)
    if (row.version if row is not None else 0) != version:
        raise _conflict(row)
    if row is None:
        db.session.add(SettingsRow(scope=scope, values_json=values, version=1, updated_by=actor.id))
        return
    changed = rows_affected(
        update(SettingsRow)
        .where(SettingsRow.scope == scope, SettingsRow.version == version)
        .values(values_json=values, version=version + 1, updated_by=actor.id, updated_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    if changed == 0:
        db.session.rollback()
        forget()
        raise _conflict(_rows().get(scope))


def store_settings(actor: User, scope: str, version: int, raw: dict[str, Any]) -> dict[str, Any]:
    require(actor, Permission.SETTINGS_EDIT)
    theme = active_theme()
    clean, errors = validate(fields(scope, theme), raw)
    if errors:
        raise invalid(errors)
    before = stored(scope)
    _write(scope, version, clean, actor)
    diff = {
        key: [before.get(key), clean.get(key)]
        for key in sorted(set(before) | set(clean))
        if before.get(key) != clean.get(key)
    }
    audit.record(
        f"settings.{scope}_updated",
        actor_id=actor.id,
        entity="settings",
        entity_id=scope,
        diff=diff,
    )
    entity_revisions.record("settings", scope, clean, actor.id)
    page_cache.mark_changed()  # il sito cambia subito (D-140)
    db.session.commit()
    forget()
    return section(scope, theme)
