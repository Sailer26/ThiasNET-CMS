"""Registro delle attività (audit_log)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.types import UtcDateTime, utcnow


class AuditLog(Base):
    __tablename__ = "audit_log"
    # D-124: filtri del registro per tipo di azione e per oggetto.
    __table_args__ = (
        Index("ix_audit_log_action_created_at", "action", "created_at"),
        Index("ix_audit_log_entity_entity_id", "entity", "entity_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None, index=True
    )
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str | None] = mapped_column(String(64), default=None)
    entity_id: Mapped[str | None] = mapped_column(String(64), default=None)
    diff_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    ip_hash: Mapped[str | None] = mapped_column(String(64), default=None)  # D-30: mai l'IP
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, index=True)
