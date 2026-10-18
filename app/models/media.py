"""Libreria media: file caricati e cartelle (D-70 … D-85)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.types import UtcDateTime, utcnow

ALT_MAX_LENGTH = 250
NAME_MAX_LENGTH = 200
FOLDER_NAME_MAX_LENGTH = 80
ROOT_FOLDER = text("parent_id IS NULL")


class MediaKind(StrEnum):
    IMAGE = "image"
    DOCUMENT = "document"  # solo PDF (D-70)


class MediaFolder(Base):
    __tablename__ = "media_folders"
    __table_args__ = (
        UniqueConstraint("parent_id", "name_key"),
        # In SQL NULL è sempre diverso da NULL: nella radice serve un indice a parte.
        Index(
            "uq_media_folders_root_name",
            "name_key",
            unique=True,
            sqlite_where=ROOT_FOLDER,
            postgresql_where=ROOT_FOLDER,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_folders.id", ondelete="RESTRICT"), default=None
    )
    name: Mapped[str] = mapped_column(String(FOLDER_NAME_MAX_LENGTH))
    name_key: Mapped[str] = mapped_column(
        String(FOLDER_NAME_MAX_LENGTH)
    )  # minuscole, senza accenti
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, onupdate=utcnow)


class Media(Base):
    __tablename__ = "media"
    __table_args__ = (
        CheckConstraint("kind IN ('image', 'document')", name="kind_valid"),
        CheckConstraint(
            "focal_x BETWEEN 0 AND 100 AND focal_y BETWEEN 0 AND 100", name="focal_valid"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    storage_key: Mapped[str] = mapped_column(String(32), unique=True)  # cartella dei file (D-74)
    kind: Mapped[str] = mapped_column(String(16))
    mime: Mapped[str] = mapped_column(String(40))
    ext: Mapped[str] = mapped_column(String(5))
    original_name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    search_key: Mapped[str] = mapped_column(String(500))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)  # doppioni (D-76)
    width: Mapped[int | None] = mapped_column(Integer, default=None)
    height: Mapped[int | None] = mapped_column(Integer, default=None)
    alt: Mapped[str] = mapped_column(String(ALT_MAX_LENGTH), default="", server_default=text("''"))
    focal_x: Mapped[int] = mapped_column(SmallInteger, default=50, server_default="50")
    focal_y: Mapped[int] = mapped_column(SmallInteger, default=50, server_default="50")
    variants_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    file_rev: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")  # D-44
    folder_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_folders.id", ondelete="RESTRICT"), default=None, index=True
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, onupdate=utcnow)
