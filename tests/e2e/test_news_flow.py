"""Notizie nel browser (7b): dalla schermata Notizie al sito, con il controllo prima di pubblicare."""

from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect
from sqlalchemy import select

from app.extensions import db
from app.models.user import User
from app.services import pages, publishing
from tests.e2e.conftest import OWNER_EMAIL
from tests.e2e.helpers import WAIT_MS, login

pytestmark = pytest.mark.e2e


def _listing_page(app: Flask) -> None:
    """La pagina «Elenco notizie» c'è già: il test parla delle notizie, non delle pagine."""
    with app.app_context():
        owner = db.session.execute(select(User).where(User.email == OWNER_EMAIL)).scalar_one()
        listing = pages.create_page(owner, title="Notizie", layout="news_list")
        publishing.publish(owner, listing, 1)


def test_news_reaches_the_site(page: Page, live_app: Flask, live_server: str) -> None:
    _listing_page(live_app)
    login(page, live_server)
    page.get_by_role("navigation", name="Menu del pannello").get_by_role(
        "link", name="Notizie"
    ).click()
    expect(page.get_by_role("heading", name="Notizie")).to_be_visible(timeout=WAIT_MS)
    page.get_by_role("button", name="Nuova notizia").click()
    dialog = page.get_by_role("dialog", name="Nuova notizia")
    dialog.get_by_label("Titolo della notizia").fill("Festa del paese")
    dialog.get_by_role("button", name="Crea").click()
    expect(page.get_by_label("Titolo", exact=True)).to_have_value(
        "Festa del paese", timeout=WAIT_MS
    )
    page.get_by_label("Data").fill("2026-10-25")
    page.get_by_label("Riassunto").fill("Tutti in piazza sabato")
    page.get_by_role("button", name="Pubblica", exact=True).click()
    confirm = page.get_by_role("dialog", name="Pubblicare la notizia?")
    confirm.get_by_role("button", name="Pubblica comunque").click()  # avviso: SEO vuota
    expect(page.get_by_text("Notizia pubblicata.")).to_be_visible(timeout=WAIT_MS)

    html = page.request.get(f"{live_server}/notizie/festa-del-paese").text()
    assert "Festa del paese" in html and "Tutti in piazza sabato" in html
    listing = page.request.get(f"{live_server}/notizie").text()
    assert 'href="/notizie/festa-del-paese"' in listing and "25 ottobre 2026" in listing
