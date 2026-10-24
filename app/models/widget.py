"""Aree widget riempite dal pannello (D-146): la lista intera per area e lingua."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.types import UtcDateTime, utcnow


class WidgetAreaRow(Base):
    __tablename__ = "widget_areas"

    area: Mapped[str] = mapped_column(String(32), primary_key=True)
    locale: Mapped[str] = mapped_column(String(5), primary_key=True)
    items_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")  # D-44
    # Il prossimo "fino al" di un banner: a quell'ora la cache del sito si rinnova.
    next_change_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), default=None, index=True)
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
