"""Menu nel browser (6b): da automatico a fatto a mano, con un link che arriva subito al sito."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.helpers import WAIT_MS, login

pytestmark = pytest.mark.e2e


def test_manual_menu_reaches_the_site(page: Page, live_server: str) -> None:
    login(page, live_server)
    page.get_by_role("button", name="Crea la homepage").click()
    page.get_by_role("dialog").get_by_role("button", name="Crea", exact=True).click()
    expect(page.get_by_role("link", name="Home", exact=True)).to_be_visible(timeout=WAIT_MS)

    page.get_by_role("navigation", name="Menu del pannello").get_by_role(
        "link", name="Menu"
    ).click()
    main = page.get_by_role("region", name="Menu principale")
    expect(main.get_by_text("si fa da solo")).to_be_visible(timeout=WAIT_MS)
    main.get_by_role("button", name="Aggiungi link").click()
    dialog = page.get_by_role("dialog", name="Aggiungi link")
    dialog.get_by_label("Testo").fill("Orari dello sportello")
    dialog.get_by_label("Indirizzo").fill("https://www.esterno.ch/orari")
    dialog.get_by_role("button", name="Aggiungi").click()
    main.get_by_role("button", name="Salva").click()
    page.get_by_role("dialog", name="Salvare il menu?").get_by_role("button", name="Salva").click()
    expect(main.get_by_text("Menu salvato")).to_be_visible(timeout=WAIT_MS)
    expect(main.get_by_role("button", name="Torna automatico")).to_be_visible()

    html = page.request.get(f"{live_server}/").text()
    assert "Orari dello sportello" in html and 'href="https://www.esterno.ch/orari"' in html
