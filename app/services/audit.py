"""Registro delle attività. La riga viene aggiunta alla sessione: la salva il commit di chi
fa la modifica, così modifica e audit stanno nella stessa transazione."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from flask import has_request_context, request
from sqlalchemy import func, select

from app.extensions import db
from app.models.audit import AuditLog
from app.services.crypto import hash_ip

SENSITIVE_KEY_RE = re.compile(r"password|secret|token|hash", re.IGNORECASE)


def _redact(value: Any) -> Any:
    """Toglie ricorsivamente le chiavi sensibili: nell'audit non finiscono mai segreti."""
    if isinstance(value, Mapping):
        return {k: _redact(v) for k, v in value.items() if not SENSITIVE_KEY_RE.search(str(k))}
    if isinstance(value, list | tuple):
        return [_redact(v) for v in value]
    return value


def record(
    action: str,
    *,
    actor_id: int | None,
    entity: str | None = None,
    entity_id: int | str | None = None,
    diff: Mapping[str, Any] | None = None,
) -> AuditLog:
    ip = request.remote_addr if has_request_context() else None
    entry = AuditLog(
        user_id=actor_id,
        action=action,
        entity=entity,
        entity_id=None if entity_id is None else str(entity_id),
        diff_json=_redact(diff) if diff else None,
        ip_hash=hash_ip(ip),
    )
    db.session.add(entry)
    return entry


def list_entries(page: int, limit: int) -> tuple[list[AuditLog], int]:
    total = db.session.execute(select(func.count()).select_from(AuditLog)).scalar_one()
    rows = db.session.execute(
        select(AuditLog).order_by(AuditLog.id.desc()).offset((page - 1) * limit).limit(limit)
    ).scalars()
    return list(rows), total


def serialize(entry: AuditLog) -> dict[str, Any]:
    """Per il pannello dell'owner. L'impronta dell'IP resta interna."""
    return {
        "id": entry.id,
        "user_id": entry.user_id,
        "action": entry.action,
        "entity": entry.entity,
        "entity_id": entry.entity_id,
        "diff": entry.diff_json,
        "created_at": entry.created_at.isoformat(),
    }
