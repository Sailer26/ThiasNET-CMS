"""Richieste "Chiedi a Thias" (D-09, D-134): conservate 12 mesi, inviate come i messaggi."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.types import UtcDateTime, utcnow

SCREEN_MAX_LENGTH = 200


class SupportRequest(Base):
    __tablename__ = "support_requests"
    __table_args__ = (Index("ix_support_requests_user_id_created_at", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    page_id: Mapped[int | None] = mapped_column(
        ForeignKey("pages.id", ondelete="SET NULL"), default=None
    )
    screen: Mapped[str] = mapped_column(String(SCREEN_MAX_LENGTH), default="")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), default=None, index=True)
    send_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(String(64), default=None)  # solo un codice
