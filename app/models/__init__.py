"""Modelli SQLAlchemy: base dichiarativa e registrazione di tutte le tabelle."""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Nomi stabili per vincoli e indici: necessari perché Alembic gestisca bene SQLite (batch mode).
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# Registra tutte le tabelle in Base.metadata (serve ad Alembic e ai test).
from app.models import audit, contact, login_attempt, media, page, site, user  # noqa: E402, F401
