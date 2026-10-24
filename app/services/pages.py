"""Pagine: creazione, slug e spostamenti, riordino, cestino (D-43, D-44, D-45, D-48).

I permessi si controllano qui (D-48): le route dichiarano `content.edit`, ma le azioni su
pagine online o programmate richiedono anche `content.publish`. Le letture e la
serializzazione stanno in `page_views.py`.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import set_committed_value

from app.extensions import db
from app.models.page import SLUG_MAX_LENGTH, TITLE_MAX_LENGTH, Page, PageDraft, PageStatus
from app.models.types import utcnow
from app.models.user import User
from app.services import audit, page_cache, page_paths, revisions
from app.services.content import empty_document
from app.services.errors import ServiceError, not_found, version_conflict
from app.services.page_paths import MAX_DEPTH, depth, live, path_for, path_taken
from app.services.page_views import is_home
from app.services.permissions import Permission, require
from app.services.sanitize import clean_line
from app.services.slugs import is_reserved, slugify, validate_slug
from app.services.sql import rows_affected
from app.services.theme import active_theme

PAGE_NOT_FOUND = "Pagina non trovata"
FALLBACK_SLUG = "pagina"
MAX_SLUG_ATTEMPTS = 500
# "Online" per i permessi (D-48): già pubblicate o con una pubblicazione in arrivo.
ONLINE_STATUSES = frozenset({PageStatus.PUBLISHED, PageStatus.SCHEDULED})
PATH_INDEX_MARKERS = ("uq_pages_locale_path", "pages.locale, pages.path")

__all__ = ["is_home", "require"]


def _path_taken_error() -> ServiceError:
    return ServiceError("path_taken", "Esiste già una pagina con questo indirizzo", 409)


def _too_deep() -> ServiceError:
    return ServiceError("too_deep", f"Al massimo {MAX_DEPTH} livelli di sottopagine", 422)


def is_online(page: Page) -> bool:
    return page.status in ONLINE_STATUSES or page.publish_at is not None


def get_page(page_id: int) -> Page:
    page = db.session.get(Page, page_id)
    if page is None or page.deleted_at is not None:
        raise not_found(PAGE_NOT_FOUND)
    return page


def get_trashed(page_id: int) -> Page:
    page = db.session.get(Page, page_id)
    if page is None or page.deleted_at is None:
        raise not_found(PAGE_NOT_FOUND)
    return page


def bump_version(page: Page, expected: int) -> None:
    """D-44: UPDATE condizionato; se qualcun altro ha salvato prima → 409."""
    if page.version != expected:
        raise version_conflict(page.version, page.updated_by, page.updated_at)
    statement = (
        update(Page)
        .where(Page.id == page.id, Page.version == expected)
        .values(version=expected + 1)
        .execution_options(synchronize_session=False)
    )
    if rows_affected(statement) != 1:
        db.session.rollback()
        fresh = db.session.get_one(Page, page.id)
        raise version_conflict(fresh.version, fresh.updated_by, fresh.updated_at)
    set_committed_value(page, "version", expected + 1)


@contextmanager
def _unique_path_guard() -> Iterator[None]:
    """Con richieste parallele decide l'indice unico (lingua, path): 409 invece di 500.
    Le altre violazioni di vincoli sono bug veri e restano errori."""
    try:
        yield
    except IntegrityError as exc:
        db.session.rollback()
        if any(marker in str(exc.orig) for marker in PATH_INDEX_MARKERS):
            raise _path_taken_error() from exc
        raise


# --- Creazione -----------------------------------------------------------------


def _title(raw: str) -> str:
    title = clean_line(raw)
    if not title or len(title) > TITLE_MAX_LENGTH:
        raise ServiceError(
            "invalid_title", f"Il titolo è obbligatorio (massimo {TITLE_MAX_LENGTH})", 422
        )
    return title


def _listing_has_no_children() -> ServiceError:
    return ServiceError(
        "listing_has_no_children",
        "Sotto la pagina delle notizie ci sono le notizie: niente sottopagine",
        422,
    )


def is_listing(page: Page) -> bool:
    layout = active_theme().layouts.get(page.layout)
    return layout is not None and layout.collection is not None


def check_listing(page: Page | None, layout: str, locale: str) -> None:
    """D-149: una sola pagina elenco per raccolta e lingua, e senza sottopagine."""
    spec = active_theme().layouts.get(layout)
    if spec is None or spec.collection is None:
        return
    query = select(Page.id).where(live(), Page.locale == locale, Page.layout == layout)
    if page is not None:
        query = query.where(Page.id != page.id)
    if db.session.execute(query.limit(1)).first() is not None:
        raise ServiceError(
            "listing_exists", "C'è già una pagina che elenca queste notizie in questa lingua", 409
        )
    if page is not None and page_paths.has_children(page):
        raise _listing_has_no_children()


def _parent(parent_id: int | None, locale: str) -> Page | None:
    if parent_id is None:
        return None
    parent = get_page(parent_id)
    if is_listing(parent):
        raise _listing_has_no_children()
    if is_home(parent):
        raise ServiceError("home_has_no_children", "La homepage non può avere sottopagine", 422)
    if parent.locale != locale:
        raise ServiceError(
            "parent_locale_mismatch", "La pagina superiore è in un'altra lingua", 422
        )
    if depth(parent.path) + 1 > MAX_DEPTH:
        raise _too_deep()
    return parent


def _check_slug(slug: str, parent: Page | None) -> None:
    validate_slug(slug)
    if parent is None and is_reserved(slug):
        raise ServiceError(
            "reserved_slug", "Questo indirizzo è riservato al sistema: scegline un altro", 422
        )


def _free_slug(base: str, parent: Page | None, locale: str) -> str:
    for attempt in range(1, MAX_SLUG_ATTEMPTS + 1):
        suffix = "" if attempt == 1 else f"-{attempt}"
        candidate = base[: SLUG_MAX_LENGTH - len(suffix)].rstrip("-") + suffix
        reserved = parent is None and is_reserved(candidate)
        if not reserved and not path_taken(locale, path_for(parent, candidate)):
            return candidate
    raise ServiceError("slug_taken", "Non trovo un indirizzo libero: indicane uno", 409)


def _parent_is(parent_id: int | None) -> ColumnElement[bool]:
    return Page.parent_id.is_(None) if parent_id is None else Page.parent_id == parent_id


def _next_sort(parent_id: int | None, locale: str) -> int:
    query = select(func.max(Page.sort)).where(live(), Page.locale == locale, _parent_is(parent_id))
    current = db.session.execute(query).scalar_one()
    return 0 if current is None else current + 1


def _home_path(locale: str, *, has_parent: bool) -> str:
    if has_parent:
        raise ServiceError("home_has_no_parent", "La homepage non sta sotto un'altra pagina", 422)
    if path_taken(locale, page_paths.HOME_PATH):
        raise ServiceError("home_exists", "Esiste già una homepage per questa lingua", 409)
    return page_paths.HOME_PATH


def _new_address(
    title: str, slug: str | None, parent_id: int | None, locale: str
) -> tuple[str, str, Page | None]:
    """(slug, path, genitore) di una pagina nuova: homepage, slug automatico o indicato."""
    if slug == "":
        return "", _home_path(locale, has_parent=parent_id is not None), None
    parent = _parent(parent_id, locale)
    if slug is None:
        slug = _free_slug(slugify(title) or FALLBACK_SLUG, parent, locale)
    else:
        _check_slug(slug, parent)
        if path_taken(locale, path_for(parent, slug)):
            raise ServiceError("slug_taken", "Esiste già una pagina con questo indirizzo", 409)
    path = path_for(parent, slug)
    page_paths.check_length([path])
    return slug, path, parent


def create_page(
    actor: User,
    *,
    title: str,
    layout: str,
    locale: str | None = None,
    parent_id: int | None = None,
    slug: str | None = None,
) -> Page:
    theme = active_theme()
    clean_title = _title(title)
    locale = locale or theme.locales[0]
    if locale not in theme.locales:
        raise ServiceError("unknown_locale", "Lingua non attiva in questo sito", 422)
    if layout not in theme.layouts:
        raise ServiceError("unknown_layout", "Layout non disponibile nel tema", 422)
    check_listing(None, layout, locale)
    slug, path, parent = _new_address(clean_title, slug, parent_id, locale)
    parent_key = None if parent is None else parent.id
    page = Page(
        parent_id=parent_key,
        locale=locale,
        translation_group=str(uuid.uuid4()),
        slug=slug,
        path=path,
        title=clean_title,
        layout=layout,
        seo_json={},
        sort=_next_sort(parent_key, locale),
        created_by=actor.id,
        updated_by=actor.id,
    )
    with _unique_path_guard():
        db.session.add(page)
        db.session.flush()
        page_paths.clear_redirects(locale, [path])
        db.session.add(
            PageDraft(
                page_id=page.id,
                data_json=empty_document(theme, clean_title, layout),
                author_id=actor.id,
            )
        )
        audit.record(
            "page.created",
            actor_id=actor.id,
            entity="page",
            entity_id=page.id,
            diff={"title": clean_title, "locale": locale, "path": path, "layout": layout},
        )
        db.session.commit()
    return page


# --- Slug e spostamenti -----------------------------------------------------------


def _new_parent(page: Page, parent_id: int | None, branch: list[Page]) -> Page | None:
    if parent_id is None:
        return None
    parent = get_page(parent_id)
    if any(p.id == parent.id for p in branch):
        raise ServiceError("cycle", "Una pagina non può stare sotto una sua sottopagina", 422)
    if is_listing(parent):
        raise _listing_has_no_children()
    if is_home(parent):
        raise ServiceError("home_has_no_children", "La homepage non può avere sottopagine", 422)
    if parent.locale != page.locale:
        raise ServiceError(
            "parent_locale_mismatch", "La pagina superiore è in un'altra lingua", 422
        )
    return parent


def _plan_move(
    actor: User, page: Page, new_slug: str, new_parent_id: int | None
) -> tuple[list[Page], dict[int, str]]:
    """Verifica uno spostamento e restituisce il ramo con i suoi nuovi path."""
    branch = page_paths.subtree(page)
    parent = _new_parent(page, new_parent_id, branch)
    _check_slug(new_slug, parent)
    new_root = path_for(parent, new_slug)
    if depth(new_root) + page_paths.height(branch, page) - 1 > MAX_DEPTH:
        raise _too_deep()
    new_paths = page_paths.rebased_paths(branch, page, new_root)
    page_paths.check_length(new_paths.values())
    if page_paths.any_path_taken(page.locale, new_paths.values(), exclude=[p.id for p in branch]):
        raise _path_taken_error()
    if any(is_online(p) for p in branch):
        require(actor, Permission.PUBLISH)  # D-45/D-48: cambia l'indirizzo di pagine online
    return branch, new_paths


def update_page(actor: User, page: Page, *, version: int, changes: Mapping[str, Any]) -> Page:
    """Cambia slug e/o genitore; ricalcola i percorsi del ramo e registra i 301."""
    new_slug = changes.get("slug", page.slug)
    new_parent_id = changes.get("parent_id", page.parent_id)
    if is_home(page) and (new_slug != "" or new_parent_id is not None):
        raise ServiceError("home_is_fixed", "L'indirizzo della homepage non si può cambiare", 422)
    if version != page.version:
        raise version_conflict(page.version, page.updated_by, page.updated_at)
    if new_slug == page.slug and new_parent_id == page.parent_id:
        return page
    branch, new_paths = _plan_move(actor, page, new_slug, new_parent_id)
    diff: dict[str, Any] = {"path": [page.path, new_paths[page.id]]}
    if new_slug != page.slug:
        diff["slug"] = [page.slug, new_slug]
    moved = new_parent_id != page.parent_id
    if moved:
        diff["parent_id"] = [page.parent_id, new_parent_id]
    sort = _next_sort(new_parent_id, page.locale) if moved else page.sort  # in fondo ai fratelli
    with _unique_path_guard():
        bump_version(page, version)
        page_paths.apply_paths(branch, new_paths)
        page.slug, page.parent_id, page.sort = new_slug, new_parent_id, sort
        page.updated_by = actor.id
        page_cache.mark_changed()
        action = "page.moved" if moved else "page.slug_changed"
        audit.record(action, actor_id=actor.id, entity="page", entity_id=page.id, diff=diff)
        db.session.commit()
    return page


def reorder(actor: User, *, parent_id: int | None, locale: str, ids: Sequence[int]) -> None:
    """Ordine delle sorelle: va elencata ogni pagina, una volta sola."""
    query = select(Page).where(live(), Page.locale == locale, _parent_is(parent_id))
    children = {p.id: p for p in db.session.execute(query).scalars()}
    if len(ids) != len(set(ids)) or set(ids) != set(children):
        raise ServiceError(
            "reorder_mismatch", "L'elenco non corrisponde alle pagine: ricarica e riprova", 422
        )
    for position, page_id in enumerate(ids):
        children[page_id].sort = position
    page_cache.mark_changed()  # l'ordine del menu automatico (D-58)
    audit.record(
        "page.reordered",
        actor_id=actor.id,
        entity="page",
        entity_id=parent_id,
        diff={"locale": locale, "ids": list(ids)},
    )
    db.session.commit()


# --- Cestino -------------------------------------------------------------------


def trash(actor: User, page: Page, version: int) -> Page:
    """D-43: si cestina, non si elimina; la pagina va subito offline."""
    if is_home(page):
        raise ServiceError("home_protected", "La homepage non si può cestinare", 409)
    if page_paths.has_children(page):
        raise ServiceError("has_children", "Sposta o cestina prima le sottopagine", 409)
    if is_online(page):
        require(actor, Permission.PUBLISH)
    previous = page.status
    bump_version(page, version)
    revisions.cancel_schedule(page.id)
    page_paths.drop_redirects_of(page.id)
    page.deleted_at, page.deleted_by, page.updated_by = utcnow(), actor.id, actor.id
    page.status, page.publish_at, page.published_at = PageStatus.DRAFT, None, None
    page_cache.mark_changed()
    audit.record(
        "page.trashed",
        actor_id=actor.id,
        entity="page",
        entity_id=page.id,
        diff={"path": page.path, "status": previous},
    )
    db.session.commit()
    return page


def restore(actor: User, page: Page, version: int) -> Page:
    """Torna come bozza non pubblicata, sotto la stessa pagina superiore."""
    parent = None
    if page.parent_id is not None:
        parent = db.session.get(Page, page.parent_id)
        if parent is None or parent.deleted_at is not None:
            raise ServiceError("parent_trashed", "Ripristina prima la pagina superiore", 409)
        if depth(parent.path) + 1 > MAX_DEPTH:
            raise _too_deep()
    path = path_for(parent, page.slug)  # il genitore può essere stato spostato nel frattempo
    page_paths.check_length([path])
    if path_taken(page.locale, path, exclude=[page.id]):
        raise _path_taken_error()
    with _unique_path_guard():
        bump_version(page, version)
        page_paths.clear_redirects(page.locale, [path])
        page.path, page.deleted_at, page.deleted_by = path, None, None
        page.status, page.updated_by = PageStatus.DRAFT, actor.id
        audit.record(
            "page.restored",
            actor_id=actor.id,
            entity="page",
            entity_id=page.id,
            diff={"path": path},
        )
        db.session.commit()
    return page
