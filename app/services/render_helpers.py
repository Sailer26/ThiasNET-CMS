"""Pezzi di HTML prodotti dal CMS per i temi (D-56, D-60): mai template, solo testo escapato.

- `head_markup`: title, description, canonical, robots, variabili CSS;
- `body_end_markup`: banner del consenso e script del CMS (file statici, niente JS inline);
- `embed`: indirizzi di video e mappe costruiti da dati già validati;
- filtri `safe_html` e `clean_url` per i template.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from markupsafe import Markup

from app.services import render_media
from app.services.public_texts import month, text
from app.services.render_context import BlockView, PageContext, RenderMode
from app.services.sanitize import clean_rich, is_safe_url

YOUTUBE_ID = re.compile(r"[A-Za-z0-9_-]{11}")
VIMEO_ID = re.compile(r"[0-9]{1,12}")
VIMEO_HASH = re.compile(r"[0-9a-f]{6,20}")  # video privati (D-129)
CONSENT_SCRIPT = "/static/cms/consent.js"
PREVIEW_SCRIPT = "/static/cms/preview.js"
MIN_ZOOM, MAX_ZOOM, DEFAULT_ZOOM = 1, 19, 15


def safe_html(value: object) -> Markup:
    """Il rich text si ri-pulisce sempre all'uscita (D-53): anche dati salvati male."""
    return Markup(clean_rich(value)) if isinstance(value, str) else Markup("")  # noqa: S704


def clean_url(value: object) -> str:
    return value if isinstance(value, str) and is_safe_url(value) else ""


def _video(data: Mapping[str, Any]) -> dict[str, str] | None:
    provider, video_id = data.get("provider"), data.get("video_id")
    if not isinstance(video_id, str):
        return None
    if provider == "youtube" and YOUTUBE_ID.fullmatch(video_id):
        return {
            "src": f"https://www.youtube-nocookie.com/embed/{video_id}",
            "link": f"https://www.youtube.com/watch?v={video_id}",
            "provider": "YouTube",
        }
    if provider == "vimeo" and VIMEO_ID.fullmatch(video_id):
        secret = data.get("video_hash")
        private = f"h={secret}&" if isinstance(secret, str) and VIMEO_HASH.fullmatch(secret) else ""
        return {
            "src": f"https://player.vimeo.com/video/{video_id}?{private}dnt=1",
            "link": f"https://vimeo.com/{video_id}" + (f"/{secret}" if private else ""),
            "provider": "Vimeo",
        }
    return None


def _number(value: object, low: float, high: float) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) and low <= number <= high else None


def _map(data: Mapping[str, Any]) -> dict[str, str] | None:
    lat, lng = _number(data.get("lat"), -90, 90), _number(data.get("lng"), -180, 180)
    if lat is None or lng is None:
        return None
    raw_zoom = data.get("zoom")
    zoom = DEFAULT_ZOOM
    if isinstance(raw_zoom, int) and not isinstance(raw_zoom, bool):
        zoom = raw_zoom if MIN_ZOOM <= raw_zoom <= MAX_ZOOM else DEFAULT_ZOOM
    span = 180 / 2**zoom
    bbox = f"{lng - span:.5f},{lat - span / 2:.5f},{lng + span:.5f},{lat + span / 2:.5f}"
    query = urlencode({"bbox": bbox, "layer": "mapnik", "marker": f"{lat:.5f},{lng:.5f}"})
    return {
        "src": f"https://www.openstreetmap.org/export/embed.html?{query}",
        "link": f"https://www.openstreetmap.org/?mlat={lat:.5f}&mlon={lng:.5f}#map={zoom}/{lat:.5f}/{lng:.5f}",
        "provider": "OpenStreetMap",
    }


def embed(block: BlockView) -> Mapping[str, str] | None:
    """Dati del segnaposto "clicca per caricare" (D-60). Il tema non costruisce URL."""
    found = _video(block.data) if block.type == "video" else None
    if block.type == "map":
        found = _map(block.data)
    if found is None:
        return None
    kind = "video" if block.type == "video" else "map"
    title = block.data.get("title") or block.data.get("label") or found["provider"]
    return {**found, "kind": kind, "title": str(title)}


def _alternates(context: PageContext) -> list[Markup]:
    """hreflang (D-151): solo le lingue con la traduzione online, e x-default sulla prima."""
    found = [language for language in context.languages if language.translated]
    if len(found) < 2:
        return []
    base = context.site.base_url
    link = Markup('<link rel="alternate" hreflang="{}" href="{}">')
    links = [link.format(language.locale, base + language.url) for language in found]
    default = next((x for x in found if x.locale == context.site.locale), None)
    if default is not None:
        links.append(link.format("x-default", base + default.url))
    return links


def head_markup(context: PageContext) -> Markup:
    page, site = context.page, context.site
    seo_title = page.seo.get("title")
    if isinstance(seo_title, str) and seo_title:
        title = seo_title
    elif site.name and page.title and page.title != site.name:
        title = f"{page.title} | {site.name}"
    else:
        title = page.title or site.name
    parts = [Markup("<title>{}</title>").format(title)]
    description = page.seo.get("description")
    if isinstance(description, str) and description:
        parts.append(Markup('<meta name="description" content="{}">').format(description))
    if context.mode is RenderMode.PREVIEW or page.noindex:
        parts.append(Markup('<meta name="robots" content="noindex">'))
    parts.append(Markup('<link rel="canonical" href="{}">').format(site.base_url + page.path))
    parts.extend(_alternates(context))
    parts.append(
        Markup('<link rel="stylesheet" href="/_vars.css?v={}">').format(context.css_version)
    )
    text_description = description if isinstance(description, str) else None
    parts.append(render_media.social_markup(context, title, text_description))
    return Markup("\n").join(parts)


def _consent_banner(locale: str, with_stats: bool) -> Markup:
    def t(key: str) -> str:
        return text(key, locale)

    stats = (
        Markup('<label><input type="checkbox" name="stats"> {}</label>').format(t("consent_stats"))
        if with_stats
        else Markup("")
    )
    return Markup(
        '<div class="cms-consent" id="cms-consent" role="dialog" aria-modal="false" '
        'aria-labelledby="cms-consent-title" hidden>'
        '<h2 class="cms-consent__title" id="cms-consent-title">{title}</h2>'
        '<p class="cms-consent__text">{text}</p>'
        '<div class="cms-consent__choices" id="cms-consent-choices" hidden>'
        '<label><input type="checkbox" name="embeds"> {embeds}</label>{stats}</div>'
        '<div class="cms-consent__actions">'
        '<button type="button" class="cms-consent__button" data-cms-consent="all">{all}</button>'
        '<button type="button" class="cms-consent__button" data-cms-consent="necessary">'
        "{necessary}</button>"
        '<button type="button" class="cms-consent__button cms-consent__button--link" '
        'data-cms-consent="choose" aria-expanded="false" aria-controls="cms-consent-choices">'
        "{choose}</button>"
        '<button type="button" class="cms-consent__button" data-cms-consent="save" hidden>'
        "{save}</button>"
        "</div></div>"
    ).format(
        title=t("consent_title"),
        text=t("consent_text"),
        embeds=t("consent_embeds"),
        stats=stats,
        all=t("consent_accept_all"),
        necessary=t("consent_necessary"),
        choose=t("consent_choose"),
        save=t("consent_save"),
    )


def body_end_markup(context: PageContext) -> Markup:
    # Nell'anteprima del pannello niente statistiche: le visite di chi lavora non contano.
    analytics = None if context.mode is RenderMode.PREVIEW else context.analytics
    parts = [_consent_banner(context.page.locale, analytics is not None)]
    if analytics is not None:
        parts.append(
            Markup(
                '<script src="{}" defer data-matomo-url="{}" data-matomo-site="{}"></script>'
            ).format(CONSENT_SCRIPT, analytics.url, analytics.site_id)
        )
    else:
        parts.append(Markup('<script src="{}" defer></script>').format(CONSENT_SCRIPT))
    if context.mode is RenderMode.PREVIEW:
        parts.append(Markup('<script src="{}" defer></script>').format(PREVIEW_SCRIPT))
    return Markup("\n").join(parts)


def image_placeholder(locale: str) -> Markup:
    return Markup(
        '<span class="cms-media-placeholder" role="img" aria-label="{0}">{0}</span>'
    ).format(text("image_placeholder", locale))


def format_date(value: object, locale: str, style: str = "long") -> str:
    """Una data del CMS ("AAAA-MM-GG" o istante ISO) come la legge un visitatore:
    "24 ottobre 2026" (style "long") o "24.10.2026" (style "short"). Valore strano → vuoto."""
    if not isinstance(value, str):
        return ""
    try:
        moment = datetime.fromisoformat(value if "T" in value else f"{value}T00:00")
    except ValueError:
        return ""
    if style == "short":
        return f"{moment.day:02d}.{moment.month:02d}.{moment.year}"
    return f"{moment.day} {month(moment.month, locale)} {moment.year}"
