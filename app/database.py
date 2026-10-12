"""Impostazioni del database: SQLite in WAL con chiavi esterne attive."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine, make_url

# busy_timeout per primo: anche il passaggio a WAL deve aspettare un lock invece di fallire.
SQLITE_PRAGMAS = (
    "PRAGMA busy_timeout=5000",
    "PRAGMA journal_mode=WAL",
    "PRAGMA foreign_keys=ON",
)


# Listener globale voluto: vale per ogni engine SQLite del processo (app, Alembic, test),
# così nessuna connessione gira senza chiavi esterne. Gli altri database sono ignorati.
@event.listens_for(Engine, "connect")
def _configure_sqlite(dbapi_connection: Any, _connection_record: Any) -> None:
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    try:
        for pragma in SQLITE_PRAGMAS:
            cursor.execute(pragma)
    finally:
        cursor.close()


def ensure_sqlite_directory(database_uri: str) -> None:
    """Crea la cartella del file SQLite se manca (es. `data/` in sviluppo)."""
    url = make_url(database_uri)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        return
    Path(url.database).parent.mkdir(parents=True, exist_ok=True)
