"""Menu fatti a mano dal pannello (D-141, D-145): albero intero per posizione e lingua."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.types import UtcDateTime, utcnow


class MenuRow(Base):
    __tablename__ = "menus"

    location: Mapped[str] = mapped_column(String(32), primary_key=True)
    locale: Mapped[str] = mapped_column(String(5), primary_key=True)
    items_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")  # D-44
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
