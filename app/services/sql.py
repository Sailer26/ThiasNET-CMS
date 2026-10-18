"""Piccoli aiuti SQL condivisi dai servizi."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import Executable
from sqlalchemy.engine import CursorResult

from app.extensions import db


def rows_affected(statement: Executable) -> int:
    """Esegue un UPDATE/DELETE e dice quante righe ha toccato: base dei controlli
    "solo se nessun altro l'ha già fatto" (blocco ottimistico, D-44)."""
    result = cast(CursorResult[Any], db.session.execute(statement))
    return result.rowcount
