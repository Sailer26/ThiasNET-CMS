"""Menu del sito (D-140, D-141, D-145).

Un menu si salva intero (albero annidato) con una versione: il pannello non manda mai
"parent_id", quindi non si possono creare cicli. Le voci di pagina tengono solo l'id: titolo e
indirizzo si leggono al momento di mostrare il sito, e una pagina non online sparisce con le
sue sottovoci. Il menu "main" resta automatico (D-58) finché qualcuno non lo salva.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.menu import MenuRow
from app.models.page import Page, PageStatus
from app.models.types import utcnow
from app.models.user import User
from app.services import audit, entity_revisions, page_cache, public_pages
from app.services.blocks import FieldError
from app.services.content import invalid
from app.services.errors import ServiceError, not_found, version_conflict
from app.services.page_paths import live
from app.services.permissions import Permission, require
from app.services.render_context import Link
from app.services.sanitize import clean_line, is_safe_url, normalize_url
from app.services.sql import rows_affected
from app.services.theme import Theme

AUTOMATIC = "main"  # D-141: l'unico menu che si fa da solo
MAX_ITEMS = 60
LABEL_MAX_LENGTH = 80
URL_MAX_LENGTH = 2048
MAX_ID = 2**31 - 1
UID_RE = re.compile(r"^[0-9a-f]{32}$")
ITEM_KEYS = frozenset({"uid", "label", "page_id", "url", "children"})
SUBJECT = "questo menu"
MESSAGES = {
    "invalid_shape": "Voce non valida",
    "invalid_uid": "Voce non valida",
    "duplicate_uid": "Voce ripetuta",
    "invalid_target": "Scegli una pagina oppure scrivi un indirizzo",
    "label_required": "Serve un testo per il link",
    "max_length": f"Al massimo {LABEL_MAX_LENGTH} caratteri",
    "invalid_url": "Indirizzo non valido: usa https://, mailto:, tel: o un percorso con /",
    "page_missing": "La pagina non c'è più (o è nel cestino)",
    "too_deep": "Troppi livelli per questo menu",
    "too_many": f"Al massimo {MAX_ITEMS} voci",
}


def _problem(path: str, code: str) -> FieldError:
    return FieldError(path, code, MESSAGES[code])


def _locale(theme: Theme) -> str:
    return theme.locales[0]  # D-94: il pannello lavora nella lingua principale


def spec(theme: Theme, location: str) -> Mapping[str, Any]:
    found: Mapping[str, Any] | None = theme.menus.get(location)
    if found is None:
        raise not_found("Menu non previsto dal tema")
    return found


def _row(location: str, locale: str) -> MenuRow | None:
    return db.session.get(MenuRow, (location, locale))


# --- Validazione -------------------------------------------------------------------------------


@dataclass
class _Check:
    max_depth: int
    errors: list[FieldError] = field(default_factory=list)
    uids: set[str] = field(default_factory=set)
    pages: dict[int, list[str]] = field(default_factory=dict)  # id -> percorsi che lo usano


def _count(items: Any) -> int:
    if not isinstance(items, list):
        return 0
    return sum(1 + _count(i.get("children") if isinstance(i, dict) else None) for i in items)


def _target(raw: dict[str, Any], path: str, check: _Check) -> dict[str, Any] | None:
    page_id, url = raw.get("page_id"), raw.get("url")
    if (page_id is None) == (url is None):
        check.errors.append(_problem(path, "invalid_target"))
        return None
    if page_id is not None:
        if isinstance(page_id, bool) or not isinstance(page_id, int) or not 1 <= page_id <= MAX_ID:
            check.errors.append(_problem(f"{path}/page_id", "page_missing"))
            return None
        check.pages.setdefault(page_id, []).append(f"{path}/page_id")
        return {"page_id": page_id}
    target = normalize_url(url.strip()) if isinstance(url, str) else ""
    if not target or len(target) > URL_MAX_LENGTH or not is_safe_url(target):
        check.errors.append(_problem(f"{path}/url", "invalid_url"))
        return None
    return {"url": target}


def _label(raw: dict[str, Any], path: str, check: _Check, needed: bool) -> str | None:
    label = raw.get("label")
    if label is not None and not isinstance(label, str):
        check.errors.append(_problem(f"{path}/label", "invalid_shape"))
        return None
    text = clean_line(label or "")
    if len(text) > LABEL_MAX_LENGTH:
        check.errors.append(_problem(f"{path}/label", "max_length"))
    elif needed and not text:
        check.errors.append(_problem(f"{path}/label", "label_required"))
    return text or None


def _item(raw: Any, path: str, depth: int, check: _Check) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or not set(raw) <= ITEM_KEYS:
        check.errors.append(_problem(path, "invalid_shape"))
        return None
    uid = raw.get("uid")
    if not isinstance(uid, str) or not UID_RE.fullmatch(uid):
        check.errors.append(_problem(f"{path}/uid", "invalid_uid"))
    elif uid in check.uids:
        check.errors.append(_problem(f"{path}/uid", "duplicate_uid"))
    else:
        check.uids.add(uid)
    target = _target(raw, path, check)
    label = _label(raw, path, check, needed=target is not None and "url" in target)
    children = _items(raw.get("children", []), f"{path}/children", depth + 1, check)
    if target is None or not isinstance(uid, str):
        return None
    return {"uid": uid, **({"label": label} if label else {}), **target, "children": children}


def _items(raw: Any, path: str, depth: int, check: _Check) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        check.errors.append(_problem(path, "invalid_shape"))
        return []
    if raw and depth > check.max_depth:
        check.errors.append(_problem(path, "too_deep"))
        return []
    found = (_item(child, f"{path}/{index}", depth, check) for index, child in enumerate(raw))
    return [item for item in found if item is not None]


def _check_pages(check: _Check, locale: str) -> None:
    if not check.pages:
        return
    query = select(Page.id).where(Page.id.in_(check.pages), live(), Page.locale == locale)
    existing = set(db.session.execute(query).scalars())
    for page_id, paths in check.pages.items():
        if page_id not in existing:
            check.errors.extend(_problem(path, "page_missing") for path in paths)


def validate(
    items: Any, max_depth: int, locale: str
) -> tuple[list[dict[str, Any]], list[FieldError]]:
    if _count(items) > MAX_ITEMS:
        return [], [_problem("items", "too_many")]
    check = _Check(max_depth=max_depth)
    clean = _items(items, "items", 1, check)
    _check_pages(check, locale)
    return clean, check.errors


# --- Lettura per il pannello ---------------------------------------------------------------------


def _automatic_items(location: str, locale: str) -> list[dict[str, Any]]:
    if location != AUTOMATIC:
        return []
    return [
        {"uid": uuid.uuid4().hex, "page_id": page.id, "children": []}
        for page in public_pages.auto_pages(locale)
    ]


def editable(location: str, theme: Theme) -> dict[str, Any]:
    found = spec(theme, location)
    locale = _locale(theme)
    row = _row(location, locale)
    return {
        "location": location,
        "label": found["label"],
        "max_depth": found["max_depth"],
        "automatic": location == AUTOMATIC,
        "manual": row is not None,
        "version": row.version if row is not None else 0,
        "items": list(row.items_json) if row is not None else _automatic_items(location, locale),
    }


def all_editable(theme: Theme) -> list[dict[str, Any]]:
    return [editable(location, theme) for location in theme.menus]


# --- Scrittura -----------------------------------------------------------------------------------


def _conflict(row: MenuRow | None) -> ServiceError:
    if row is None:
        return version_conflict(0, None, None, SUBJECT)
    return version_conflict(row.version, row.updated_by, row.updated_at, SUBJECT)


def _write(
    location: str, locale: str, version: int, items: list[dict[str, Any]], actor: User
) -> int:
    row = _row(location, locale)
    if (row.version if row is not None else 0) != version:
        raise _conflict(row)
    if row is None:  # due primi salvataggi insieme: lo decide il commit
        db.session.add(
            MenuRow(location=location, locale=locale, items_json=items, updated_by=actor.id)
        )
        return 1
    changed = rows_affected(
        update(MenuRow)
        .where(MenuRow.location == location, MenuRow.locale == locale, MenuRow.version == version)
        .values(items_json=items, version=version + 1, updated_by=actor.id, updated_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    if changed == 0:
        db.session.rollback()
        raise _conflict(_row(location, locale))
    return version + 1


def _commit(location: str, locale: str) -> None:
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise _conflict(_row(location, locale)) from None


def store_menu(
    actor: User, location: str, version: int, items: Any, theme: Theme
) -> dict[str, Any]:
    """D-140: chi può pubblicare salva il menu, e il sito cambia subito."""
    require(actor, Permission.PUBLISH)
    found = spec(theme, location)
    locale = _locale(theme)
    clean, errors = validate(items, int(found["max_depth"]), locale)
    if errors:
        raise invalid(errors)
    before = _row(location, locale)
    old_count = _count(before.items_json) if before is not None else 0
    new_version = _write(location, locale, version, clean, actor)
    diff = {"items": [old_count, _count(clean)]}
    audit.record("menu.updated", actor_id=actor.id, entity="menu", entity_id=location, diff=diff)
    snapshot = {"version": new_version, "items": clean}
    entity_revisions.record("menu", f"{location}:{locale}", snapshot, actor.id)
    page_cache.mark_changed()
    _commit(location, locale)
    return editable(location, theme)


def reset_menu(actor: User, location: str, version: int, theme: Theme) -> dict[str, Any]:
    """ "Torna automatico" (D-141): il menu fatto a mano si toglie; "main" torna automatico."""
    require(actor, Permission.PUBLISH)
    spec(theme, location)
    locale = _locale(theme)
    row = _row(location, locale)
    if row is None:
        return editable(location, theme)
    removed = rows_affected(
        delete(MenuRow).where(
            MenuRow.location == location, MenuRow.locale == locale, MenuRow.version == version
        )
    )
    if removed == 0:
        db.session.rollback()
        raise _conflict(_row(location, locale))
    audit.record("menu.reset", actor_id=actor.id, entity="menu", entity_id=location)
    entity_revisions.record(
        "menu", f"{location}:{locale}", {"version": None, "items": None}, actor.id
    )
    page_cache.mark_changed()
    db.session.commit()
    db.session.expire_all()  # la riga cancellata non deve restare nella sessione
    return editable(location, theme)


# --- Lettura per il sito -------------------------------------------------------------------------


def _page_ids(items: Any) -> Iterator[int]:
    for item in items or ():
        if isinstance(item, dict):
            if isinstance(item.get("page_id"), int):
                yield item["page_id"]
            yield from _page_ids(item.get("children"))


def _online(ids: set[int], locale: str) -> dict[int, Page]:
    if not ids:
        return {}
    query = select(Page).where(
        Page.id.in_(ids), live(), Page.locale == locale, Page.status == PageStatus.PUBLISHED
    )
    return {page.id: page for page in db.session.execute(query).scalars()}


@dataclass(frozen=True)
class _Build:
    pages: Mapping[int, Page]
    current: Page | None
    theme: Theme
    max_depth: int


def _links(items: Any, depth: int, build: _Build) -> tuple[Link, ...]:
    found: list[Link] = []
    for item in items or ():
        if not isinstance(item, dict):
            continue
        children = _links(item.get("children"), depth + 1, build) if depth < build.max_depth else ()
        label = item.get("label")
        if isinstance(item.get("page_id"), int):
            page = build.pages.get(item["page_id"])
            if page is None:
                continue  # non online: sparisce con le sottovoci
            url = public_pages.public_url(page, build.theme)
            current = public_pages.is_current(page, build.current)
            found.append(Link(label or page.title, url, current, children))
        elif isinstance(item.get("url"), str) and is_safe_url(item["url"]) and label:
            found.append(Link(label, item["url"], False, children))
    return tuple(found)


def links(location: str, locale: str, current: Page | None, theme: Theme) -> tuple[Link, ...]:
    row = _row(location, locale)
    if row is None:
        return public_pages.auto_menu(locale, current, theme) if location == AUTOMATIC else ()
    max_depth = int(theme.menus[location]["max_depth"])  # un tema che riduce i livelli taglia
    pages = _online(set(_page_ids(row.items_json)), locale)
    return _links(row.items_json, 1, _Build(pages, current, theme, max_depth))


def site_menus(locale: str, current: Page | None, theme: Theme) -> Mapping[str, tuple[Link, ...]]:
    return MappingProxyType(
        {location: links(location, locale, current, theme) for location in theme.menus}
    )
