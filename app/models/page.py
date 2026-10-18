"""Pagine, blocchi pubblicati, revisioni, bozze e reindirizzamenti (D-38, D-40, D-45).

- `pages` + `blocks`: la versione pubblicata (quella che il sito mostrerà dalla Fase 3);
- `page_drafts`: la copia di lavoro, un documento JSON unico salvato dall'autosave;
- `page_revisions`: istantanee per lo storico e la pubblicazione programmata;
- `page_redirects`: vecchi indirizzi di pagine online, per il 301 automatico.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core_types import BLOCK_TYPES
from app.models import Base
from app.models.types import UtcDateTime, utcnow


class PageStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"  # online
    SCHEDULED = "scheduled"  # mai pubblicata, in attesa della data (D-47)


class RevisionKind(StrEnum):
    PUBLISHED = "published"
    SCHEDULED = "scheduled"  # istantanea congelata in attesa: al massimo una per pagina
    UNPUBLISHED = "unpublished"
    DRAFT = "draft"  # bozza messa da parte prima di un ripristino o programmazione fallita


PAGE_STATUSES = tuple(PageStatus)
REVISION_KINDS = tuple(RevisionKind)
LOCALE_LENGTH = 5
SLUG_MAX_LENGTH = 80
PATH_MAX_LENGTH = 255
TITLE_MAX_LENGTH = 200
NAME_MAX_LENGTH = 64  # layout e zone: nomi definiti dal tema


def _in(column: str, values: tuple[str, ...] | list[str]) -> str:
    """CHECK da valori fissi del codice (enum e BLOCK_TYPES), mai da input utente."""
    return f"{column} IN ({', '.join(f"'{v}'" for v in values)})"


LIVE = text("deleted_at IS NULL")
SCHEDULED = text(f"kind = '{RevisionKind.SCHEDULED}'")


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (
        CheckConstraint(_in("status", PAGE_STATUSES), name="status_valid"),
        Index(
            "uq_pages_locale_path",
            "locale",
            "path",
            unique=True,
            sqlite_where=LIVE,
            postgresql_where=LIVE,
        ),
        Index("ix_pages_status_publish_at", "status", "publish_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("pages.id", ondelete="RESTRICT"), default=None, index=True
    )
    locale: Mapped[str] = mapped_column(String(LOCALE_LENGTH))
    translation_group: Mapped[str] = mapped_column(String(36), index=True)  # Fase 7
    slug: Mapped[str] = mapped_column(String(SLUG_MAX_LENGTH))
    path: Mapped[str] = mapped_column(String(PATH_MAX_LENGTH))
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH))
    layout: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    status: Mapped[str] = mapped_column(
        String(16), default=PageStatus.DRAFT, server_default=PageStatus.DRAFT.value
    )
    publish_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), default=None)
    published_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), default=None)
    seo_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    sort: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
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


class Block(Base):
    """Un blocco della versione pubblicata. La bozza vive in `page_drafts.data_json`."""

    __tablename__ = "blocks"
    __table_args__ = (
        CheckConstraint(_in("type", sorted(BLOCK_TYPES)), name="type_valid"),
        UniqueConstraint("page_id", "uid"),
        Index("ix_blocks_page_id_zone_sort", "page_id", "zone", "sort"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    uid: Mapped[str] = mapped_column(String(32))  # D-39
    zone: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    type: Mapped[str] = mapped_column(String(32))
    variant: Mapped[str | None] = mapped_column(String(NAME_MAX_LENGTH), default=None)
    data_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class PageRevision(Base):
    __tablename__ = "page_revisions"
    __table_args__ = (
        CheckConstraint(_in("kind", REVISION_KINDS), name="kind_valid"),
        Index("ix_page_revisions_page_id_created_at", "page_id", "created_at"),
        Index(
            "uq_page_revisions_scheduled",
            "page_id",
            unique=True,
            sqlite_where=SCHEDULED,
            postgresql_where=SCHEDULED,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class PageDraft(Base):
    __tablename__ = "page_drafts"

    page_id: Mapped[int] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE"), primary_key=True
    )
    data_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")  # D-44
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, onupdate=utcnow)


class PageRedirect(Base):
    """Vecchio indirizzo di una pagina online: il sito risponde 301 verso il nuovo (Fase 3)."""

    __tablename__ = "page_redirects"
    __table_args__ = (UniqueConstraint("locale", "from_path"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), index=True)
    locale: Mapped[str] = mapped_column(String(LOCALE_LENGTH))
    from_path: Mapped[str] = mapped_column(String(PATH_MAX_LENGTH))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
