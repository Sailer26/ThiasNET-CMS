"""Widget nel browser (6c): un widget nel piè di pagina arriva subito al sito."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.helpers import WAIT_MS, login

pytestmark = pytest.mark.e2e


def test_footer_widget_reaches_the_site(page: Page, live_server: str) -> None:
    login(page, live_server)
    page.get_by_role("button", name="Crea la homepage").click()
    page.get_by_role("dialog").get_by_role("button", name="Crea", exact=True).click()
    expect(page.get_by_role("link", name="Home", exact=True)).to_be_visible(timeout=WAIT_MS)

    page.get_by_role("navigation", name="Menu del pannello").get_by_role(
        "link", name="Widget"
    ).click()
    footer = page.get_by_role("region", name="Piè di pagina")
    expect(footer.get_by_text("Ancora nessun widget qui.")).to_be_visible(timeout=WAIT_MS)
    footer.get_by_label("Quale widget?").select_option(label="Contatti")
    footer.get_by_role("button", name="Aggiungi widget").click()
    dialog = page.get_by_role("dialog", name="Aggiungi: Contatti")
    dialog.get_by_label("Titolo").fill("Dove trovarci")
    dialog.get_by_role("button", name="Fatto").click()
    expect(footer.get_by_text("Dove trovarci")).to_be_visible()
    footer.get_by_role("button", name="Salva").click()
    confirm = page.get_by_role("dialog", name="Salvare questa parte del sito?")
    confirm.get_by_role("button", name="Salva").click()
    expect(footer.get_by_text("il sito è già aggiornato")).to_be_visible(timeout=WAIT_MS)

    html = page.request.get(f"{live_server}/").text()
    assert "Dove trovarci" in html and "data-widget-id=" in html
