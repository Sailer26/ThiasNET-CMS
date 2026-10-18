"""Messaggi del modulo contatti (D-05, D-61, D-67): conservati 12 mesi."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.types import UtcDateTime, utcnow

NAME_MAX_LENGTH = 120
EMAIL_MAX_LENGTH = 254
PHONE_MAX_LENGTH = 30
MESSAGE_MAX_LENGTH = 5000


class ContactMessage(Base):
    __tablename__ = "contact_messages"
    __table_args__ = (Index("ix_contact_messages_ip_hash_created_at", "ip_hash", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    form_page_id: Mapped[int | None] = mapped_column(
        ForeignKey("pages.id", ondelete="SET NULL"), default=None
    )
    block_uid: Mapped[str] = mapped_column(String(32))
    locale: Mapped[str] = mapped_column(String(5))
    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH))
    phone: Mapped[str | None] = mapped_column(String(PHONE_MAX_LENGTH), default=None)
    message: Mapped[str] = mapped_column(Text)
    ip_hash: Mapped[str] = mapped_column(String(64))  # D-30: mai l'IP in chiaro
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), default=None, index=True)
    send_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(String(64), default=None)  # solo un codice
