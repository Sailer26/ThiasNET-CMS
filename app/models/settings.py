"""Impostazioni salvate dal pannello (D-143): una riga per ambito ("site", "appearance")."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.types import UtcDateTime, utcnow


class SettingsRow(Base):
    __tablename__ = "settings"

    scope: Mapped[str] = mapped_column(String(20), primary_key=True)
    values_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")  # D-44
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
