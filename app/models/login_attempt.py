"""Tentativi di login falliti, per il rate limit condiviso tra worker (D-24)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.types import UtcDateTime, utcnow


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # HMAC di email e IP: il database non contiene dati personali in chiaro.
    email_key: Mapped[str] = mapped_column(String(64), index=True)
    ip_key: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, index=True)
