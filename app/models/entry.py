"""Voci delle raccolte del tema, es. le notizie (D-147).

- `entries`: la versione pubblicata (titolo, campi, SEO) e lo stato, come `pages`;
- `entry_drafts`: la copia di lavoro, un documento `{title, fields, seo}`;
- l'istantanea programmata sta in `entries.scheduled_json` (le versioni passate in
  `entity_revisions`, D-139, che ne tiene 50).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.page import LOCALE_LENGTH, NAME_MAX_LENGTH, SLUG_MAX_LENGTH, TITLE_MAX_LENGTH
from app.models.types import UtcDateTime, utcnow


class EntryStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"  # online
    SCHEDULED = "scheduled"  # mai pubblicata, in attesa della data (D-47)


ENTRY_STATUSES = tuple(EntryStatus)
LIVE = text("deleted_at IS NULL")
STATUS_CHECK = "status IN ('draft', 'published', 'scheduled')"


class Entry(Base):
    __tablename__ = "entries"
    __table_args__ = (
        CheckConstraint(STATUS_CHECK, name="status_valid"),
        Index(
            "uq_entries_locale_collection_slug",
            "locale",
            "collection",
            "slug",
            unique=True,
            sqlite_where=LIVE,
            postgresql_where=LIVE,
        ),
        Index("ix_entries_listing", "collection", "locale", "status", "sort_at"),
        Index("ix_entries_publish_at", "publish_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    collection: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    locale: Mapped[str] = mapped_column(String(LOCALE_LENGTH))
    translation_group: Mapped[str] = mapped_column(String(36), index=True)  # 7c
    slug: Mapped[str] = mapped_column(String(SLUG_MAX_LENGTH))
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH))
    fields_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    seo_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(
        String(16), default=EntryStatus.DRAFT, server_default=EntryStatus.DRAFT.value
    )
    publish_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), default=None)
    published_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), default=None)
    # Ordine dell'elenco: la prima data obbligatoria della raccolta, altrimenti la pubblicazione.
    sort_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), default=None)
    scheduled_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    scheduled_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")  # D-44
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), default=None)  # D-43
    deleted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )


class EntryDraft(Base):
    __tablename__ = "entry_drafts"

    entry_id: Mapped[int] = mapped_column(
        ForeignKey("entries.id", ondelete="CASCADE"), primary_key=True
    )
    data_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")  # D-44
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, onupdate=utcnow)
