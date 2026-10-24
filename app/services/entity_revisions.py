"""Versioni generiche (D-139): impostazioni, menu, aree widget. Si tengono le ultime 50."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select

from app.extensions import db
from app.models.revision import EntityRevision

KEPT = 50


def record(
    entity_type: str, entity_key: str, snapshot: dict[str, Any], author_id: int | None
) -> None:
    """Non fa commit: va nella transazione di chi ha cambiato l'oggetto."""
    db.session.add(
        EntityRevision(
            entity_type=entity_type,
            entity_key=entity_key,
            snapshot_json=snapshot,
            author_id=author_id,
        )
    )
    db.session.flush()
    old = (
        select(EntityRevision.id)
        .where(EntityRevision.entity_type == entity_type, EntityRevision.entity_key == entity_key)
        .order_by(EntityRevision.created_at.desc(), EntityRevision.id.desc())
        .offset(KEPT)
    )
    stale = list(db.session.execute(old).scalars())
    if stale:
        db.session.execute(delete(EntityRevision).where(EntityRevision.id.in_(stale)))


def history(entity_type: str, entity_key: str) -> list[EntityRevision]:
    """Le versioni tenute di un oggetto, dalla più recente."""
    query = (
        select(EntityRevision)
        .where(EntityRevision.entity_type == entity_type, EntityRevision.entity_key == entity_key)
        .order_by(EntityRevision.created_at.desc(), EntityRevision.id.desc())
        .limit(KEPT)
    )
    return list(db.session.execute(query).scalars())
