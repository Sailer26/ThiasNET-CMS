"""Impostazioni nel browser (6a): nome del sito e colore del tema arrivano subito al sito."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.helpers import WAIT_MS, login

pytestmark = pytest.mark.e2e


def test_site_name_and_accent_color(page: Page, live_server: str) -> None:
    login(page, live_server)
    page.get_by_role("navigation", name="Menu del pannello").get_by_role(
        "link", name="Impostazioni"
    ).click()

    site = page.get_by_role("region", name="Dati del sito")
    site.get_by_label("Nome del sito").fill("Comune di Prova")
    site.get_by_role("button", name="Salva").click()
    expect(site.get_by_text("Impostazioni salvate")).to_be_visible(timeout=WAIT_MS)

    look = page.get_by_role("region", name="Aspetto")
    look.get_by_role("radio", name="#1F7A4D").check()
    look.get_by_role("button", name="Salva").click()
    expect(look.get_by_text("Impostazioni salvate")).to_be_visible(timeout=WAIT_MS)

    css = page.request.get(f"{live_server}/_vars.css").text()
    assert "--accent-color: #1F7A4D;" in css
