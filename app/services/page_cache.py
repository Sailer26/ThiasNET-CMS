"""Cache HTML delle pagine pubbliche (D-54).

- In memoria, per processo: niente file su disco (regola d'oro, D-21).
- Invalidazione condivisa: `site_state.cache_generation` nel database. Ogni modifica visibile
  chiama `mark_changed()` nella sua stessa transazione; ogni richiesta legge il numero e, se è
  cambiato, il processo svuota la sua cache.
- Non entrano in cache: anteprima, pagine con modulo contatti, 404, risposte a POST.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Hashable

from flask import current_app
from sqlalchemy import select, update

from app.extensions import db
from app.models.site import SITE_STATE_ID, SiteState
from app.models.types import utcnow
from app.services.sql import rows_affected

CACHE_KEY = "thiasnet.page_cache"


def current_generation() -> int:
    query = select(SiteState.cache_generation).where(SiteState.id == SITE_STATE_ID)
    value = db.session.execute(query).scalar_one_or_none()
    return 0 if value is None else value


def mark_changed() -> None:
    """Il sito è cambiato. Non fa commit: lo fa chi ha cambiato il contenuto."""
    statement = (
        update(SiteState)
        .where(SiteState.id == SITE_STATE_ID)
        .values(cache_generation=SiteState.cache_generation + 1, updated_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    if rows_affected(statement) == 0:  # database creato senza migrazioni (test)
        db.session.add(SiteState(id=SITE_STATE_ID, cache_generation=1))


class PageCache:
    """LRU per numero di pagine e per byte, protetta da lock (gunicorn con thread)."""

    def __init__(self, max_entries: int, max_bytes: int) -> None:
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self._lock = threading.Lock()
        self._entries: OrderedDict[Hashable, str] = OrderedDict()
        self._bytes = 0
        self._generation: int | None = None

    def _sync(self, generation: int) -> bool:
        """True se `generation` è quella corrente. I numeri crescono soltanto: uno più nuovo
        svuota la cache, uno più vecchio (risposta arrivata tardi) viene ignorato."""
        if self._generation is None or generation > self._generation:
            self._entries = OrderedDict()
            self._bytes = 0
            self._generation = generation
        return generation == self._generation

    def get(self, key: Hashable, generation: int) -> str | None:
        with self._lock:
            if not self._sync(generation):
                return None
            html = self._entries.get(key)
            if html is not None:
                self._entries.move_to_end(key)
            return html

    def put(self, key: Hashable, html: str, generation: int) -> None:
        size = len(html.encode("utf-8"))
        with self._lock:
            if not self._sync(generation) or size > self.max_bytes:
                return  # risposta di una generazione vecchia, o pagina troppo grande
            previous = self._entries.pop(key, None)
            if previous is not None:
                self._bytes -= len(previous.encode("utf-8"))
            self._entries[key] = html
            self._bytes += size
            while len(self._entries) > self.max_entries or self._bytes > self.max_bytes:
                _old_key, old = self._entries.popitem(last=False)
                self._bytes -= len(old.encode("utf-8"))


def page_cache() -> PageCache:
    cache = current_app.extensions.get(CACHE_KEY)
    if not isinstance(cache, PageCache):
        cache = PageCache(
            int(current_app.config["PAGE_CACHE_MAX_ENTRIES"]),
            int(current_app.config["PAGE_CACHE_MAX_BYTES"]),
        )
        current_app.extensions[CACHE_KEY] = cache
    return cache
