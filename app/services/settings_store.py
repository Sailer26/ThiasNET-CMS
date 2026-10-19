"""Lettura e salvataggio delle impostazioni (D-143, D-144): blocco ottimistico, registro,
versioni, cache del sito. Le letture si tengono come dati semplici per la durata del
contesto (una richiesta); ogni salvataggio le dimentica."""

from __future__ import annotations

import email.errors
import email.policy
import logging
import smtplib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from types import MappingProxyType
from typing import Any

from flask import current_app, g
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.settings import SettingsRow
from app.models.types import utcnow
from app.models.user import User
from app.services import audit, entity_revisions, mailer, page_cache
from app.services.content import invalid
from app.services.errors import ServiceError, version_conflict
from app.services.permissions import Permission, require
from app.services.sanitize import clean_line
from app.services.settings_fields import SITE_FIELDS, Field, lenient, schema, theme_fields, validate
from app.services.sql import rows_affected
from app.services.theme import Theme, active_theme

log = logging.getLogger("thiasnet.settings")
SCOPES = ("site", "appearance")
CACHE_KEY = "_thiasnet_settings"
SUBJECT = "queste impostazioni"
# Dati personali: nel registro si dice solo che sono cambiati (nLPD).
PERSONAL_KEYS = frozenset({"email", "phone", "address", "contact_recipient"})
SEND_ERRORS = (
    OSError,
    smtplib.SMTPException,
    mailer.MailError,
    ValueError,
    email.errors.MessageError,
)


@dataclass(frozen=True)
class Stored:
    values: Mapping[str, Any]
    version: int
    updated_by: int | None
    updated_at: datetime | None


def fields(scope: str, theme: Theme) -> tuple[Field, ...]:
    return SITE_FIELDS if scope == "site" else theme_fields(theme)


def _rows() -> dict[str, Stored]:
    cached: dict[str, Stored] | None = g.get(CACHE_KEY)
    if cached is None:
        cached = {
            row.scope: Stored(
                MappingProxyType(dict(row.values_json or {})),
                row.version,
                row.updated_by,
                row.updated_at,
            )
            for row in db.session.execute(select(SettingsRow)).scalars()
        }
        setattr(g, CACHE_KEY, cached)
    return cached


def forget() -> None:
    g.pop(CACHE_KEY, None)


def stored(scope: str) -> dict[str, Any]:
    row = _rows().get(scope)
    return dict(row.values) if row is not None else {}


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


def _conflict(row: Stored | None) -> ServiceError:
    if row is None:
        return version_conflict(0, None, None, SUBJECT)
    return version_conflict(row.version, row.updated_by, row.updated_at, SUBJECT)


def _write(scope: str, version: int, values: dict[str, Any], actor: User) -> int:
    row = _rows().get(scope)
    if (row.version if row is not None else 0) != version:
        raise _conflict(row)
    if row is None:  # il primo salvataggio; due insieme: lo decide il commit
        db.session.add(SettingsRow(scope=scope, values_json=values, version=1, updated_by=actor.id))
        return 1
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
    return version + 1


def _diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: "(modificato)" if key in PERSONAL_KEYS else [before.get(key), after.get(key)]
        for key in sorted(set(before) | set(after))
        if before.get(key) != after.get(key)
    }


def _notify_recipient_change(old: str | None, new: str | None, actor: User) -> None:
    """Chi riceveva i messaggi del sito lo sa subito se l'indirizzo cambia: un cambio
    silenzioso porterebbe altrove i dati dei visitatori (review di sicurezza 6a)."""
    if not old or old == new:
        return
    mail = EmailMessage(policy=email.policy.SMTP)
    mail["From"] = current_app.config.get("MAIL_FROM") or old
    mail["To"] = old
    site = clean_line(str(current_app.config.get("SITE_NAME", "")))
    mail["Subject"] = f"Sito {site}: cambiato l'indirizzo dei messaggi"
    mail.set_content(
        "L'indirizzo che riceve i messaggi del modulo contatti del sito è stato cambiato.\n\n"
        f"Prima: {old}\n"
        f"Ora: {new or 'quello predefinito impostato da ThiasNET'}\n"
        f"Da: {clean_line(actor.email)}\n\n"
        "Se non lo sapevi, avvisa subito ThiasNET.\n"
    )
    try:
        mailer.send(mail)
    except SEND_ERRORS:
        log.exception("avviso del cambio di destinatario non inviato")


def store_settings(actor: User, scope: str, version: int, raw: dict[str, Any]) -> dict[str, Any]:
    require(actor, Permission.SETTINGS_EDIT)
    theme = active_theme()
    clean, errors = validate(fields(scope, theme), raw)
    if errors:
        raise invalid(errors)
    # D-144: si salvano solo i valori diversi dal predefinito (un campo svuotato torna a quello).
    base = defaults(scope, theme)
    clean = {key: value for key, value in clean.items() if base.get(key) != value}
    recipient_before = effective(scope, theme).get("contact_recipient")
    before = stored(scope)
    new_version = _write(scope, version, clean, actor)
    diff = _diff(before, clean)
    audit.record(
        f"settings.{scope}_updated",
        actor_id=actor.id,
        entity="settings",
        entity_id=scope,
        diff=diff,
    )
    entity_revisions.record("settings", scope, {"version": new_version, "values": clean}, actor.id)
    page_cache.mark_changed()  # il sito cambia subito (D-140)
    try:
        db.session.commit()
    except IntegrityError:  # due primi salvataggi insieme: vince il primo
        db.session.rollback()
        forget()
        raise _conflict(_rows().get(scope)) from None
    forget()
    if scope == "site":
        _notify_recipient_change(
            recipient_before, effective(scope, theme).get("contact_recipient"), actor
        )
    return section(scope, theme)
