"""Dall'indirizzo richiesto alla pagina da mostrare (D-50, D-51).

- prima lingua del tema senza prefisso (`/chi-siamo`), le altre con prefisso (`/de/...`);
- solo pagine pubblicate e non cestinate; le programmazioni scadute passano da `ensure_due`;
- i vecchi indirizzi (`page_redirects`) danno 301 solo verso pagine online.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy import select

from app.extensions import db
from app.models.page import PATH_MAX_LENGTH, Page, PageRedirect, PageStatus
from app.services import publishing
from app.services.page_paths import HOME_PATH, live
from app.services.render_context import Link
from app.services.theme import Theme

log = logging.getLogger("thiasnet.public")
PATH_CHARS = re.compile(r"/[a-z0-9/-]*")
MAX_PUBLIC_PATH = PATH_MAX_LENGTH + 6  # "/rm" + path


class Outcome(StrEnum):
    PAGE = "page"
    REDIRECT = "redirect"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class Resolution:
    outcome: Outcome
    locale: str
    page: Page | None = None
    location: str | None = None


def _not_found(locale: str) -> Resolution:
    return Resolution(Outcome.NOT_FOUND, locale)


def _redirect(locale: str, location: str) -> Resolution:
    return Resolution(Outcome.REDIRECT, locale, location=location)


def public_path(locale: str, path: str, theme: Theme) -> str:
    """Indirizzo pubblico relativo (senza dominio) di un percorso interno."""
    if locale == theme.locales[0]:
        return path
    return f"/{locale}/" if path == HOME_PATH else f"/{locale}{path}"


def public_url(page: Page, theme: Theme) -> str:
    return public_path(page.locale, page.path, theme)


def _split(path: str, theme: Theme) -> Resolution | tuple[str, str]:
    """(lingua, percorso interno), oppure il redirect verso la forma canonica."""
    default = theme.locales[0]
    first = path.split("/")[1]
    if first == default:
        rest = path[len(default) + 1 :].rstrip("/")  # un solo salto anche con "/" finale
        return _redirect(default, rest or HOME_PATH)
    if first in theme.locales:
        if path == f"/{first}":
            return _redirect(first, f"/{first}/")
        inner = path[len(first) + 1 :]
        if inner != HOME_PATH and inner.endswith("/"):
            return _redirect(first, path.rstrip("/"))
        return first, inner
    if path != HOME_PATH and path.endswith("/"):
        return _redirect(default, path.rstrip("/"))
    return default, path


def _live_page(locale: str, path: str) -> Page | None:
    query = select(Page).where(live(), Page.locale == locale, Page.path == path)
    return db.session.execute(query).scalar_one_or_none()


def _is_online(page: Page | None) -> bool:
    return page is not None and page.deleted_at is None and page.status == PageStatus.PUBLISHED


def _publish_if_due(page: Page, now: datetime) -> None:
    """Cron in ritardo: si pubblica adesso (D-16). Questa GET scrive di proposito; se la
    pubblicazione fallisce si mostra la pagina com'è e ci riprova il cron."""
    try:
        publishing.ensure_due(page, now)
    except Exception:
        db.session.rollback()
        log.exception("pubblicazione programmata della pagina %s non riuscita", page.id)


def resolve(path: str, theme: Theme, now: datetime, *, publish_due: bool = True) -> Resolution:
    """Con `publish_due=False` non scrive nulla: una programmazione scaduta conta già come
    online (la pubblicherà il cron). Lo usa il controllo dei link (D-135)."""
    default = theme.locales[0]
    if len(path) > MAX_PUBLIC_PATH or not PATH_CHARS.fullmatch(path) or "//" in path:
        return _not_found(default)  # niente query per indirizzi impossibili
    split = _split(path, theme)
    if isinstance(split, Resolution):
        return split
    locale, inner = split
    page = _live_page(locale, inner)
    due = page is not None and page.publish_at is not None and page.publish_at <= now
    if due and publish_due and page is not None:
        _publish_if_due(page, now)
        page = _live_page(locale, inner)
    if page is not None and (_is_online(page) or (due and not publish_due)):
        return Resolution(Outcome.PAGE, locale, page=page)
    query = select(PageRedirect).where(
        PageRedirect.locale == locale, PageRedirect.from_path == inner
    )
    moved = db.session.execute(query).scalar_one_or_none()
    target = db.session.get(Page, moved.page_id) if moved is not None else None
    if target is not None and _is_online(target):
        return _redirect(locale, public_url(target, theme))
    return _not_found(locale)


def _home(locale: str) -> Page | None:
    page = _live_page(locale, HOME_PATH)
    return page if _is_online(page) else None


def auto_pages(locale: str) -> list[Page]:
    """D-58: homepage + pagine di primo livello online, nell'ordine dell'albero."""
    query = (
        select(Page)
        .where(
            live(),
            Page.locale == locale,
            Page.parent_id.is_(None),
            Page.status == PageStatus.PUBLISHED,
            Page.path != HOME_PATH,
        )
        .order_by(Page.sort, Page.id)
    )
    pages = list(db.session.execute(query).scalars())
    home = _home(locale)
    return ([home] if home is not None else []) + pages


def is_current(page: Page, current: Page | None) -> bool:
    """La voce di una pagina è "corrente" anche per le sue sottopagine (tranne la home)."""
    if current is None:
        return False
    if page.path == HOME_PATH:
        return current.path == HOME_PATH
    return current.path == page.path or current.path.startswith(f"{page.path}/")


def auto_menu(locale: str, current: Page | None, theme: Theme) -> tuple[Link, ...]:
    return tuple(
        Link(p.title, public_url(p, theme), is_current(p, current)) for p in auto_pages(locale)
    )


def breadcrumbs(page: Page, theme: Theme) -> tuple[Link, ...]:
    """Homepage, pagine superiori online e pagina corrente (che non è un link)."""
    chain: list[Page] = []
    parent_id = page.parent_id
    while parent_id is not None:
        parent = db.session.get(Page, parent_id)
        if parent is None:
            break
        chain.insert(0, parent)
        parent_id = parent.parent_id
    home = _home(page.locale)
    crumbs = [Link(home.title, public_url(home, theme))] if home and page.path != HOME_PATH else []
    crumbs += [Link(p.title, public_url(p, theme)) for p in chain if _is_online(p)]
    crumbs.append(Link(page.title, public_url(page, theme), current=True))
    return tuple(crumbs)
