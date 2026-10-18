"""Utenti del pannello (ruoli owner/admin/editor)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, Integer, String, false, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.types import UtcDateTime, utcnow

EMAIL_MAX_LENGTH = 254


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('owner', 'admin', 'editor')", name="role_valid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    can_publish: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )  # D-15
    totp_secret_enc: Mapped[str | None] = mapped_column(String(255), default=None)  # D-28
    totp_last_counter: Mapped[int | None] = mapped_column(Integer, default=None)
    session_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")  # D-26
    last_login_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), default=None)
    tour_completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), default=None)  # D-08
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, onupdate=utcnow)

    # --- Interfaccia richiesta da Flask-Login ---------------------------------
    @property
    def is_active(self) -> bool:
        return self.active

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def get_id(self) -> str:
        """Include la versione di sessione: incrementarla invalida tutte le sessioni (D-26)."""
        return f"{self.id}:{self.session_version}"

    @property
    def totp_enabled(self) -> bool:
        return self.totp_secret_enc is not None
