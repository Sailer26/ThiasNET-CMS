"""Sitemap e robots.txt (D-62). Indirizzi sempre da SITE_URL, mai dall'header della richiesta."""

from __future__ import annotations

from xml.sax.saxutils import escape

from sqlalchemy import select

from app.extensions import db
from app.models.page import Page, PageStatus
from app.services.page_paths import live
from app.services.public_pages import public_url
from app.services.theme import Theme

SITEMAP_LIMIT = 50_000  # massimo del protocollo per un singolo file
SITEMAP_HEAD = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
)


def _indexable(page: Page) -> bool:
    return not (page.seo_json or {}).get("noindex")


def sitemap_xml(theme: Theme, base_url: str) -> str:
    query = (
        select(Page)
        .where(live(), Page.status == PageStatus.PUBLISHED, Page.locale.in_(theme.locales))
        .order_by(Page.locale, Page.path)
        .limit(SITEMAP_LIMIT)
    )
    entries = []
    for page in db.session.execute(query).scalars():
        if not _indexable(page):
            continue
        location = escape(base_url + public_url(page, theme))
        modified = page.published_at or page.updated_at
        entries.append(
            f"  <url><loc>{location}</loc><lastmod>{modified.date().isoformat()}</lastmod></url>\n"
        )
    return SITEMAP_HEAD + "".join(entries) + "</urlset>\n"


def robots_txt(base_url: str, *, allow_indexing: bool) -> str:
    if not allow_indexing:  # siti di prova e sviluppo: mai nei motori di ricerca
        return "User-agent: *\nDisallow: /\n"
    return (
        f"User-agent: *\nDisallow: /_preview/\nDisallow: /api/\nSitemap: {base_url}/sitemap.xml\n"
    )
