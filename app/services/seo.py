"""Sitemap e robots.txt (D-62). Indirizzi sempre da SITE_URL, mai dall'header della richiesta."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from xml.sax.saxutils import escape

from sqlalchemy import select

from app.extensions import db
from app.models.entry import Entry, EntryStatus
from app.models.page import Page, PageStatus
from app.services import entries as entry_service
from app.services import site_languages
from app.services.page_paths import live, public_path
from app.services.theme import Theme

SITEMAP_LIMIT = 50_000  # massimo del protocollo per un singolo file
SITEMAP_HEAD = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
    'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
)


@dataclass(frozen=True)
class _Url:
    group: str  # stesso gruppo = stessa pagina in un'altra lingua (D-151)
    locale: str
    location: str
    modified: str


def _attr(value: str) -> str:
    return escape(value, {'"': "&quot;"})


def _url_xml(url: _Url, siblings: list[_Url]) -> str:
    links = "".join(
        f'<xhtml:link rel="alternate" hreflang="{_attr(s.locale)}" href="{_attr(s.location)}"/>'
        for s in (siblings if len(siblings) > 1 else ())
    )
    return (
        f"  <url><loc>{escape(url.location)}</loc><lastmod>{url.modified}</lastmod>{links}</url>\n"
    )


def sitemap_xml(theme: Theme, base_url: str) -> str:
    """Le lingue senza homepage online restano fuori (D-158)."""
    visible = site_languages.visible_locales(theme)
    query = (
        select(
            Page.locale,
            Page.path,
            Page.seo_json,
            Page.published_at,
            Page.updated_at,
            Page.translation_group,
        )
        .where(live(), Page.status == PageStatus.PUBLISHED, Page.locale.in_(visible))
        .order_by(Page.locale, Page.path)
        .limit(SITEMAP_LIMIT)
    )
    urls: list[_Url] = []
    for locale, path, seo, published_at, updated_at, group in db.session.execute(query):
        if (seo or {}).get("noindex"):
            continue
        location = base_url + public_path(locale, path, theme)
        modified = (published_at or updated_at).date().isoformat()
        urls.append(_Url(f"page:{group}", locale, location, modified))
    urls += _entry_urls(theme, base_url, visible, SITEMAP_LIMIT - len(urls))
    groups: dict[str, list[_Url]] = defaultdict(list)
    for url in urls:
        groups[url.group].append(url)
    return SITEMAP_HEAD + "".join(_url_xml(url, groups[url.group]) for url in urls) + "</urlset>\n"


def _entry_urls(theme: Theme, base_url: str, visible: tuple[str, ...], room: int) -> list[_Url]:
    """Le voci online sotto la loro pagina elenco online (D-149)."""
    found: list[_Url] = []
    for key in theme.collections:
        for locale in visible:
            listing = entry_service.listing_page(theme, key, locale, online=True)
            if listing is None or (listing.seo_json or {}).get("noindex"):
                continue
            query = (
                select(
                    Entry.slug,
                    Entry.seo_json,
                    Entry.published_at,
                    Entry.updated_at,
                    Entry.translation_group,
                )
                .where(
                    Entry.deleted_at.is_(None),
                    Entry.collection == key,
                    Entry.locale == locale,
                    Entry.status == EntryStatus.PUBLISHED,
                )
                .order_by(Entry.sort_at.desc(), Entry.id.desc())
                .limit(max(room - len(found), 0))
            )
            for slug, seo, published_at, updated_at, group in db.session.execute(query):
                if (seo or {}).get("noindex"):
                    continue
                location = base_url + entry_service.entry_url(listing, slug, theme)
                modified = (published_at or updated_at).date().isoformat()
                found.append(_Url(f"entry:{group}", locale, location, modified))
    return found


def robots_txt(base_url: str, *, allow_indexing: bool) -> str:
    if not allow_indexing:  # siti di prova e sviluppo: mai nei motori di ricerca
        return "User-agent: *\nDisallow: /\n"
    return (
        f"User-agent: *\nDisallow: /_preview/\nDisallow: /api/\nSitemap: {base_url}/sitemap.xml\n"
    )
