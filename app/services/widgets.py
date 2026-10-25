"""Widget per area (D-140, D-142, D-146).

Come i menu: la lista intera di un'area si salva con una versione, e il sito cambia subito.
I dati di ogni widget si validano con il suo schema (`app/widgets/`, stesse regole dei blocchi:
niente HTML libero, testo formattato ripulito, link sicuri). Ogni widget ha una visibilità
(tutte le pagine, solo alcune, tutte tranne alcune) e il banner può avere un "fino al": a
quell'ora la cache del sito si rinnova (dal cron o alla prima visita).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

from flask import current_app
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.core_types import ENABLED_WIDGET_TYPES, WIDGET_TYPES
from app.extensions import db
from app.models.page import Page
from app.models.types import utcnow
from app.models.user import User
from app.models.widget import WidgetAreaRow
from app.services import audit, entity_revisions, page_cache
from app.services.blocks import FieldError, Mode, join_path, load_registry, plain
from app.services.content import invalid
from app.services.errors import ServiceError, not_found, version_conflict
from app.services.page_paths import live
from app.services.permissions import Permission, require
from app.services.render_context import WidgetView
from app.services.sql import rows_affected
from app.services.theme import Theme, WidgetArea

WIDGETS_DIR = Path(__file__).resolve().parents[1] / "widgets"
REGISTRY = load_registry(WIDGETS_DIR, WIDGET_TYPES)
MAX_WIDGETS = 20
MAX_PAGES = 100
MAX_ID = 2**31 - 1
UID_RE = re.compile(r"^[0-9a-f]{32}$")
ITEM_KEYS = frozenset({"uid", "type", "data", "visibility", "until"})
MODES = ("all", "only", "except")
LATEST = "latest_entries"
NOTICE = "notice"  # l'unico widget con "fino al" (D-142)
YEARS = range(2000, 2101)  # "fino al" plausibile: niente date che non si possono convertire
SUBJECT = "questa parte del sito"
MESSAGES = {
    "invalid_shape": "Widget non valido",
    "invalid_uid": "Widget non valido",
    "duplicate_uid": "Widget ripetuto",
    "not_allowed": "Questo widget non è previsto in questa parte del sito",
    "invalid_visibility": (
        "Scegli dove mostrarlo: tutte le pagine, solo alcune o tutte tranne alcune"
    ),
    "page_missing": "Una delle pagine scelte non c'è più (o è nel cestino)",
    "invalid_until": "Data e ora non valide",
    "until_not_allowed": "Solo il banner avviso può sparire da solo a una data",
    "too_many": f"Al massimo {MAX_WIDGETS} widget per parte del sito",
    "unknown_collection": "Questa raccolta non c'è nel tema",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _problem(path: str, code: str) -> FieldError:
    return FieldError(path, code, MESSAGES[code])


def _locale(theme: Theme) -> str:
    return theme.locales[0]  # D-94


def spec(theme: Theme, area: str) -> WidgetArea:
    found = theme.widget_areas.get(area)
    if found is None:
        raise not_found("Parte del sito non prevista dal tema")
    return found


def allowed_types(area: WidgetArea) -> tuple[str, ...]:
    return tuple(kind for kind in area.widgets if kind in ENABLED_WIDGET_TYPES)


def _row(area: str, locale: str) -> WidgetAreaRow | None:
    return db.session.get(WidgetAreaRow, (area, locale))


# --- Validazione ---------------------------------------------------------------------------------


@dataclass
class _Check:
    allowed: tuple[str, ...]
    collections: frozenset[str] = frozenset()
    errors: list[FieldError] = field(default_factory=list)
    uids: set[str] = field(default_factory=set)
    pages: dict[int, list[str]] = field(default_factory=dict)


def _page_ids(pages: Any) -> bool:
    return (
        isinstance(pages, list)
        and len(pages) <= MAX_PAGES
        and all(isinstance(p, int) and not isinstance(p, bool) and 1 <= p <= MAX_ID for p in pages)
    )


def _visibility(raw: Any, path: str, check: _Check) -> dict[str, Any]:
    if raw is None:
        return {"mode": "all", "pages": []}
    shaped = isinstance(raw, dict) and not set(raw) - {"mode", "pages"}
    mode = raw.get("mode") if shaped else None
    pages: Any = raw.get("pages", []) if shaped else None
    if mode not in MODES or not _page_ids(pages):
        check.errors.append(_problem(path, "invalid_visibility"))
        return {"mode": "all", "pages": []}
    chosen = sorted(set(pages)) if mode != "all" else []
    for page_id in chosen:
        check.pages.setdefault(page_id, []).append(f"{path}/pages")
    return {"mode": mode, "pages": chosen}


def _until(raw: Any, path: str, check: _Check) -> str | None:
    if raw is None:
        return None
    try:
        moment = datetime.fromisoformat(raw) if isinstance(raw, str) else None
        if moment is None or moment.tzinfo is None or moment.year not in YEARS:
            raise ValueError(raw)
        return moment.astimezone(UTC).isoformat()
    except (ValueError, OverflowError):
        check.errors.append(_problem(path, "invalid_until"))
        return None


def _item(raw: Any, path: str, check: _Check) -> dict[str, Any] | None:
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
    kind = raw.get("type")
    if kind not in check.allowed:
        check.errors.append(_problem(f"{path}/type", "not_allowed"))
        return None
    raw_data = raw.get("data", {})
    if not isinstance(raw_data, dict):
        check.errors.append(_problem(f"{path}/data", "invalid_shape"))
        return None
    data = REGISTRY.clean(kind, raw_data)
    check.errors.extend(REGISTRY.errors(kind, data, Mode.PUBLISH, join_path(path, "data")))
    collection = data.get("collection") if kind == LATEST and isinstance(data, dict) else None
    if isinstance(collection, str) and collection not in check.collections:
        check.errors.append(_problem(f"{path}/data/collection", "unknown_collection"))
    visibility = _visibility(raw.get("visibility"), f"{path}/visibility", check)
    until = _until(raw.get("until"), f"{path}/until", check)
    if until is not None and kind != NOTICE:
        check.errors.append(_problem(f"{path}/until", "until_not_allowed"))
    if not isinstance(uid, str):
        return None
    return {"uid": uid, "type": kind, "data": data, "visibility": visibility, "until": until}


def _check_pages(check: _Check, locale: str) -> None:
    if not check.pages:
        return
    query = select(Page.id).where(Page.id.in_(list(check.pages)), live(), Page.locale == locale)
    existing = set(db.session.execute(query).scalars())
    for page_id, paths in check.pages.items():
        if page_id not in existing:
            check.errors.extend(_problem(path, "page_missing") for path in dict.fromkeys(paths))


def validate(
    items: Any, area: WidgetArea, locale: str, collections: Iterable[str] = ()
) -> tuple[list[dict[str, Any]], list[FieldError]]:
    if not isinstance(items, list):
        return [], [_problem("items", "invalid_shape")]
    if len(items) > MAX_WIDGETS:
        return [], [_problem("items", "too_many")]
    check = _Check(allowed=allowed_types(area), collections=frozenset(collections))
    found = [_item(raw, f"items/{index}", check) for index, raw in enumerate(items)]
    _check_pages(check, locale)
    return [item for item in found if item is not None], check.errors


# --- Lettura per il pannello ---------------------------------------------------------------------


def _schema_for(kind: str, theme: Theme) -> dict[str, Any]:
    """Lo schema per il pannello; per "ultime notizie" la scelta della raccolta viene dal tema."""
    schema: dict[str, Any] = plain(REGISTRY.schema(kind))
    if kind == LATEST:
        keys = list(theme.collections)
        titles = [c.label for c in theme.collections.values()]
        field = {**schema["properties"]["collection"], "enum": keys, "x-enum-titles": titles}
        schema = {**schema, "properties": {**schema["properties"], "collection": field}}
    return schema


def _types(area: WidgetArea, theme: Theme) -> list[dict[str, Any]]:
    return [
        {"type": kind, "label": REGISTRY.schema(kind)["title"], "schema": _schema_for(kind, theme)}
        for kind in allowed_types(area)
    ]


def editable(area_name: str, theme: Theme) -> dict[str, Any]:
    area = spec(theme, area_name)
    row = _row(area_name, _locale(theme))
    return {
        "area": area_name,
        "label": area.label,
        "locale": _locale(theme),  # le pagine della visibilità sono di questa lingua
        "types": _types(area, theme),
        "version": row.version if row is not None else 0,
        "items": list(row.items_json) if row is not None else [],
    }


def all_editable(theme: Theme) -> list[dict[str, Any]]:
    return [editable(name, theme) for name in theme.widget_areas]


# --- Scrittura -----------------------------------------------------------------------------------


def _next_change(items: Iterable[Mapping[str, Any]], now: datetime) -> datetime | None:
    moments = (item.get("until") for item in items)
    future = [
        m for m in (datetime.fromisoformat(v) for v in moments if isinstance(v, str)) if m > now
    ]
    return min(future, default=None)


def _conflict(row: WidgetAreaRow | None) -> ServiceError:
    if row is None:
        return version_conflict(0, None, None, SUBJECT)
    return version_conflict(row.version, row.updated_by, row.updated_at, SUBJECT)


def _write(area: str, locale: str, version: int, items: list[dict[str, Any]], actor: User) -> int:
    row = _row(area, locale)
    if (row.version if row is not None else 0) != version:
        raise _conflict(row)
    next_change = _next_change(items, _now())
    if row is None:  # due primi salvataggi insieme: lo decide il commit
        db.session.add(
            WidgetAreaRow(
                area=area,
                locale=locale,
                items_json=items,
                next_change_at=next_change,
                updated_by=actor.id,
            )
        )
        return 1
    changed = rows_affected(
        update(WidgetAreaRow)
        .where(
            WidgetAreaRow.area == area,
            WidgetAreaRow.locale == locale,
            WidgetAreaRow.version == version,
        )
        .values(
            items_json=items,
            version=version + 1,
            next_change_at=next_change,
            updated_by=actor.id,
            updated_at=utcnow(),
        )
        .execution_options(synchronize_session=False)
    )
    if changed == 0:
        db.session.rollback()
        raise _conflict(_row(area, locale))
    return version + 1


def store_area(
    actor: User, area_name: str, version: int, items: Any, theme: Theme
) -> dict[str, Any]:
    """D-140: chi può pubblicare cambia i widget, e il sito cambia subito."""
    require(actor, Permission.PUBLISH)
    area = spec(theme, area_name)
    locale = _locale(theme)
    clean, errors = validate(items, area, locale, theme.collections)
    if errors:
        raise invalid(errors)
    before = _row(area_name, locale)
    old_count = len(before.items_json) if before is not None else 0
    new_version = _write(area_name, locale, version, clean, actor)
    diff = {"items": [old_count, len(clean)]}
    audit.record(
        "widget.area_updated",
        actor_id=actor.id,
        entity="widget_area",
        entity_id=area_name,
        diff=diff,
    )
    snapshot = {"version": new_version, "items": clean}
    entity_revisions.record("widget_area", f"{area_name}:{locale}", snapshot, actor.id)
    page_cache.mark_changed()
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise _conflict(_row(area_name, locale)) from None
    return editable(area_name, theme)


@dataclass(frozen=True)
class _Expiry:
    generation: int
    next_due: datetime | None


EXPIRY_KEY = "thiasnet_widget_expiry"


def _known_expiry() -> _Expiry | None:
    found = current_app.extensions.get(EXPIRY_KEY)
    return found if isinstance(found, _Expiry) else None


def expire_due(generation: int | None = None) -> bool:
    """Un banner è scaduto: la cache del sito si rinnova (una volta) e si segna il prossimo.

    Con `generation` (la route pubblica) il prossimo "fino al" si ricorda per processo: finché la
    generazione non cambia (ogni salvataggio la cambia) e quell'ora non arriva, niente query."""
    now = _now()
    known = _known_expiry()
    fresh = generation is not None and known is not None and known.generation == generation
    if fresh and known is not None and (known.next_due is None or now < known.next_due):
        return False
    query = select(WidgetAreaRow).where(
        WidgetAreaRow.next_change_at.is_not(None), WidgetAreaRow.next_change_at <= now
    )
    due = list(db.session.execute(query).scalars())
    if due:
        for row in due:
            row.next_change_at = _next_change(row.items_json, now)
        page_cache.mark_changed()
        db.session.commit()
    if generation is not None:
        upcoming = select(func.min(WidgetAreaRow.next_change_at))
        next_due = db.session.execute(upcoming).scalar_one_or_none()
        current = page_cache.current_generation() if due else generation
        current_app.extensions[EXPIRY_KEY] = _Expiry(current, next_due)
    return bool(due)


# --- Lettura per il sito -------------------------------------------------------------------------


def _visible(item: Mapping[str, Any], page_id: int | None, now: datetime) -> bool:
    until = item.get("until")
    if isinstance(until, str) and datetime.fromisoformat(until) <= now:
        return False
    visibility = item.get("visibility") or {}
    mode, pages = visibility.get("mode", "all"), set(visibility.get("pages") or ())
    if mode == "all":
        return True
    if page_id is None:  # pagina non trovata: solo i widget per tutte le pagine
        return False
    return bool((page_id in pages) == (mode == "only"))


def _views(
    row: WidgetAreaRow | None, area: WidgetArea, page_id: int | None, now: datetime
) -> tuple[WidgetView, ...]:
    allowed = allowed_types(area)
    return tuple(
        WidgetView(
            id=item["uid"], type=item["type"], data=MappingProxyType(dict(item.get("data") or {}))
        )
        for item in (row.items_json if row is not None else ())
        if item.get("type") in allowed and _visible(item, page_id, now)
    )


def site_widgets(
    locale: str, page_id: int | None, theme: Theme
) -> Mapping[str, tuple[WidgetView, ...]]:
    query = select(WidgetAreaRow).where(WidgetAreaRow.locale == locale)
    rows = {row.area: row for row in db.session.execute(query).scalars()}
    now = _now()
    return MappingProxyType(
        {
            name: _views(rows.get(name), area, page_id, now)
            for name, area in theme.widget_areas.items()
        }
    )
