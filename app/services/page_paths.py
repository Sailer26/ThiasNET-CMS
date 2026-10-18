"""Percorsi delle pagine nell'albero e reindirizzamenti dei vecchi indirizzi (D-45).

Il `path` è salvato su ogni pagina e resta coerente con l'albero: cambiando slug o genitore
si ricalcola per tutto il ramo nella stessa transazione. Il livello di una pagina è il numero
di segmenti del suo path ("/a" = 1, "/a/b/c/d" = 4).
"""

from __future__ import annotations

from collections.abc import Collection, Mapping

from sqlalchemy import ColumnElement, delete, func, select

from app.extensions import db
from app.models.page import PATH_MAX_LENGTH, Page, PageRedirect
from app.services.errors import ServiceError

MAX_DEPTH = 4
HOME_PATH = "/"


def live() -> ColumnElement[bool]:
    return Page.deleted_at.is_(None)


def path_for(parent: Page | None, slug: str) -> str:
    if slug == "":
        return HOME_PATH
    return f"{parent.path}/{slug}" if parent is not None else f"/{slug}"


def depth(path: str) -> int:
    return 0 if path == HOME_PATH else path.count("/")


def subtree(page: Page) -> list[Page]:
    """La pagina e tutti i suoi discendenti non cestinati (stessa lingua)."""
    if page.path == HOME_PATH:
        return [page]
    query = select(Page).where(
        live(),
        Page.locale == page.locale,
        (Page.id == page.id) | Page.path.startswith(f"{page.path}/", autoescape=True),
    )
    return list(db.session.execute(query.order_by(Page.path)).scalars())


def height(branch: list[Page], root: Page) -> int:
    """Livelli occupati dal ramo: 1 per una pagina senza figlie."""
    return max(depth(p.path) for p in branch) - depth(root.path) + 1


def has_children(page: Page) -> bool:
    query = select(func.count()).select_from(Page).where(live(), Page.parent_id == page.id)
    return db.session.execute(query).scalar_one() > 0


def path_taken(locale: str, path: str, exclude: Collection[int] = ()) -> bool:
    query = (
        select(func.count())
        .select_from(Page)
        .where(live(), Page.locale == locale, Page.path == path)
    )
    if exclude:
        query = query.where(Page.id.not_in(exclude))
    return db.session.execute(query).scalar_one() > 0


def any_path_taken(locale: str, paths: Collection[str], exclude: Collection[int] = ()) -> bool:
    query = (
        select(func.count())
        .select_from(Page)
        .where(live(), Page.locale == locale, Page.path.in_(list(paths)))
    )
    if exclude:
        query = query.where(Page.id.not_in(exclude))
    return db.session.execute(query).scalar_one() > 0


def check_length(paths: Collection[str]) -> None:
    """Quattro livelli di slug lunghi possono superare la colonna: meglio un 422 che un 500."""
    if any(len(path) > PATH_MAX_LENGTH for path in paths):
        raise ServiceError(
            "path_too_long",
            f"L'indirizzo completo supera {PATH_MAX_LENGTH} caratteri: accorcia gli slug",
            422,
        )


def rebased_paths(branch: list[Page], root: Page, new_root_path: str) -> dict[int, str]:
    return {p.id: new_root_path + p.path[len(root.path) :] for p in branch}


def clear_redirects(locale: str, paths: Collection[str]) -> None:
    """Una pagina vera vince sempre su un vecchio indirizzo che puntava altrove."""
    if paths:
        db.session.execute(
            delete(PageRedirect).where(
                PageRedirect.locale == locale, PageRedirect.from_path.in_(paths)
            )
        )


def drop_redirects_of(page_id: int) -> None:
    db.session.execute(delete(PageRedirect).where(PageRedirect.page_id == page_id))


def apply_paths(branch: list[Page], new_paths: Mapping[int, str]) -> list[tuple[str, str]]:
    """Aggiorna i path del ramo. Per le pagine online il vecchio indirizzo diventa un 301."""
    if not branch:
        return []
    locale = branch[0].locale
    clear_redirects(locale, list(new_paths.values()))
    changed: list[tuple[str, str]] = []
    for page in branch:
        old, new = page.path, new_paths[page.id]
        if old == new:
            continue
        page.path = new
        changed.append((old, new))
        if page.status == "published":
            clear_redirects(locale, [old])
            db.session.add(PageRedirect(page_id=page.id, locale=locale, from_path=old))
    return changed
