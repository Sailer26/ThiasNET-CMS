"""Sitemap e robots.txt (D-62). Indirizzi sempre da SITE_URL, mai dall'header della richiesta."""

from __future__ import annotations

from xml.sax.saxutils import escape

from sqlalchemy import select

from app.extensions import db
from app.models.entry import Entry, EntryStatus
from app.models.page import Page, PageStatus
from app.services import entries as entry_service
from app.services.page_paths import live
from app.services.public_pages import public_path
from app.services.theme import Theme

SITEMAP_LIMIT = 50_000  # massimo del protocollo per un singolo file
SITEMAP_HEAD = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
)


def sitemap_xml(theme: Theme, base_url: str) -> str:
    query = (
        select(Page.locale, Page.path, Page.seo_json, Page.published_at, Page.updated_at)
        .where(live(), Page.status == PageStatus.PUBLISHED, Page.locale.in_(theme.locales))
        .order_by(Page.locale, Page.path)
        .limit(SITEMAP_LIMIT)
    )
    entries = []
    for locale, path, seo, published_at, updated_at in db.session.execute(query):
        if (seo or {}).get("noindex"):
            continue
        location = escape(base_url + public_path(locale, path, theme))
        modified = published_at or updated_at
        entries.append(
            f"  <url><loc>{location}</loc><lastmod>{modified.date().isoformat()}</lastmod></url>\n"
        )
    entries += _entry_urls(theme, base_url, SITEMAP_LIMIT - len(entries))
    return SITEMAP_HEAD + "".join(entries) + "</urlset>\n"


def _entry_urls(theme: Theme, base_url: str, room: int) -> list[str]:
    """Le voci online sotto la loro pagina elenco online (D-149)."""
    found: list[str] = []
    for key in theme.collections:
        for locale in theme.locales:
            listing = entry_service.listing_page(theme, key, locale, online=True)
            if listing is None or (listing.seo_json or {}).get("noindex"):
                continue
            query = (
                select(Entry.slug, Entry.seo_json, Entry.published_at, Entry.updated_at)
                .where(
                    Entry.deleted_at.is_(None),
                    Entry.collection == key,
                    Entry.locale == locale,
                    Entry.status == EntryStatus.PUBLISHED,
                )
                .order_by(Entry.sort_at.desc(), Entry.id.desc())
                .limit(max(room - len(found), 0))
            )
            for slug, seo, published_at, updated_at in db.session.execute(query):
                if (seo or {}).get("noindex"):
                    continue
                location = escape(base_url + entry_service.entry_url(listing, slug, theme))
                modified = (published_at or updated_at).date().isoformat()
                found.append(f"  <url><loc>{location}</loc><lastmod>{modified}</lastmod></url>\n")
    return found


def robots_txt(base_url: str, *, allow_indexing: bool) -> str:
    if not allow_indexing:  # siti di prova e sviluppo: mai nei motori di ricerca
        return "User-agent: *\nDisallow: /\n"
    return (
        f"User-agent: *\nDisallow: /_preview/\nDisallow: /api/\nSitemap: {base_url}/sitemap.xml\n"
    )
