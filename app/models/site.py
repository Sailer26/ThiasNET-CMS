"""Stato condiviso del sito tra i processi del server (D-54)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.types import UtcDateTime, utcnow

SITE_STATE_ID = 1


class SiteState(Base):
    """Una sola riga. `cache_generation` cresce a ogni modifica visibile sul sito: ogni
    processo, alla richiesta successiva, vede il numero nuovo e svuota la sua cache."""

    __tablename__ = "site_state"
    __table_args__ = (CheckConstraint(f"id = {SITE_STATE_ID}", name="single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cache_generation: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, onupdate=utcnow)
