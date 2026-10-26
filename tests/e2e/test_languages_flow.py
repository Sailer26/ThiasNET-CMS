"""Lingue nel browser (7c): homepage tedesca, traduzione dall'editor, selettore sul sito."""

from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect
from sqlalchemy import select

from app.extensions import db
from app.models.page import Page as PageRow
from app.models.user import User
from app.services import drafts, pages, publishing
from tests.e2e.conftest import OWNER_EMAIL
from tests.e2e.helpers import WAIT_MS, login

pytestmark = pytest.mark.e2e


def _owner() -> User:
    return db.session.execute(select(User).where(User.email == OWNER_EMAIL)).scalar_one()


def _italian_site(app: Flask) -> int:
    """Homepage e "Chi siamo" online in italiano: il test parla delle traduzioni."""
    with app.app_context():
        owner = _owner()
        home = pages.create_page(owner, title="Home", layout="home", slug="")
        publishing.publish(owner, home, 1)
        about = pages.create_page(owner, title="Chi siamo", layout="page")
        publishing.publish(owner, about, 1)
        return about.id


def _publish_german(app: Flask) -> None:
    with app.app_context():
        owner = _owner()
        query = select(PageRow).where(PageRow.locale == "de", PageRow.deleted_at.is_(None))
        for row in db.session.execute(query).scalars():
            publishing.publish(owner, row, drafts.view(row)["version"])


def test_translation_reaches_the_site(page: Page, live_app: Flask, live_server: str) -> None:
    about_id = _italian_site(live_app)
    login(page, live_server)

    language = page.get_by_label("Lingua")
    language.select_option("de")
    page.get_by_role("button", name="Crea la homepage in Deutsch").click()
    expect(page.get_by_text("Homepage in Deutsch creata", exact=False)).to_be_visible(
        timeout=WAIT_MS
    )

    page.goto(f"{live_server}/admin/pagine/{about_id}")
    expect(page.get_by_label("Titolo della pagina")).to_have_value("Chi siamo", timeout=WAIT_MS)
    page.get_by_role("button", name="Traduzioni").click()
    page.get_by_role("button", name="Traduci in Deutsch").click()
    expect(page).not_to_have_url(f"{live_server}/admin/pagine/{about_id}", timeout=WAIT_MS)
    expect(language).to_have_value("de")

    _publish_german(live_app)
    html = page.request.get(f"{live_server}/chi-siamo").text()
    assert 'class="language-switcher"' in html
    assert 'hreflang="de" href="/de/chi-siamo"' in html
    assert '<link rel="alternate" hreflang="x-default"' in html
    assert page.request.get(f"{live_server}/de/chi-siamo").status == 200
