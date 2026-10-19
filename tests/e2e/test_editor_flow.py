"""Percorso completo nel browser (D-114): accesso, homepage, blocco di testo, salvataggio,
anteprima live, annulla, pubblicazione; la storia del browser non si riempie con l'anteprima."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import OWNER_EMAIL
from tests.helpers import PASSWORD

pytestmark = pytest.mark.e2e
TEXT = "Benvenuti a Prova"
WAIT_MS = 15_000


def _login(page: Page, base: str) -> None:
    page.goto(f"{base}/admin/")
    page.get_by_label("Email").fill(OWNER_EMAIL)
    page.get_by_label("Password").fill(PASSWORD)
    page.get_by_role("button", name="Accedi").click()
    expect(page.get_by_role("heading", name="Pagine")).to_be_visible()


def test_write_preview_undo_publish(page: Page, live_server: str) -> None:
    _login(page, live_server)
    page.get_by_role("button", name="Crea la homepage").click()
    page.get_by_role("dialog").get_by_role("button", name="Crea", exact=True).click()
    page.get_by_role("link", name="Home", exact=True).click()
    expect(page.get_by_label("Titolo della pagina")).to_have_value("Home")
    history = page.evaluate("history.length")

    zone = page.get_by_role("region", name="Contenuto principale")
    zone.get_by_role("button", name="Aggiungi blocco").click()
    page.get_by_role("dialog").get_by_role("button", name=re.compile(r"^Testo Paragrafi")).click()
    page.get_by_role("textbox", name="Testo (obbligatorio)", exact=True).click()
    page.keyboard.type(TEXT)
    expect(page.get_by_text(re.compile(r"^Salvato alle"))).to_be_visible(timeout=WAIT_MS)

    preview = page.frame_locator("iframe.preview__frame:not(.preview__frame--loading)")
    expect(preview.get_by_text(TEXT)).to_be_visible(timeout=WAIT_MS)

    page.keyboard.press("Control+z")  # annulla del pannello, anche dentro TipTap (D-105)
    expect(
        page.get_by_role("textbox", name="Testo (obbligatorio)", exact=True)
    ).not_to_contain_text(TEXT)
    page.keyboard.press("Control+y")
    expect(page.get_by_role("textbox", name="Testo (obbligatorio)", exact=True)).to_contain_text(
        TEXT
    )
    # Tornati al testo già salvato: niente da salvare.
    expect(
        page.get_by_role("status").filter(has_text=re.compile(r"^(Tutto salvato|Salvato alle)"))
    ).to_be_visible(timeout=WAIT_MS)

    page.get_by_role("button", name="Pubblica", exact=True).click()
    dialog = page.get_by_role("dialog", name="Pubblicare la pagina?")
    # Controllo prima di pubblicare (D-135): manca la descrizione per Google, si può pubblicare lo stesso.
    expect(dialog.get_by_text("Manca la descrizione per i motori di ricerca")).to_be_visible(
        timeout=WAIT_MS
    )
    dialog.get_by_role("button", name="Pubblica comunque").click()
    expect(page.get_by_text("Pagina pubblicata.")).to_be_visible(timeout=WAIT_MS)

    assert TEXT in page.request.get(f"{live_server}/").text()
    # Gli aggiornamenti dell'anteprima non aggiungono voci alla storia (D-107).
    assert page.evaluate("history.length") == history
