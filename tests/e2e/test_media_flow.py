"""Pagina Media nel browser (5c-1): caricamento multiplo, testo alternativo, punto focale,
eliminazione; un file usato in una pagina non si elimina."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.helpers import WAIT_MS, login
from tests.media_fixtures import PDF_BYTES, image_bytes

pytestmark = pytest.mark.e2e


def test_upload_alt_focal_delete(page: Page, live_server: str, tmp_path: Path) -> None:
    photo = tmp_path / "lago.png"
    photo.write_bytes(image_bytes(size=(1200, 800), color=(30, 90, 160)))
    pdf = tmp_path / "orari.pdf"
    pdf.write_bytes(PDF_BYTES)

    login(page, live_server)
    page.get_by_role("link", name="Media", exact=True).click()
    page.get_by_label("Carica file").set_input_files([str(photo), str(pdf)])
    queue = page.get_by_role("region", name="Caricamento")
    expect(queue.get_by_text("Fatto")).to_have_count(2, timeout=WAIT_MS)
    expect(page.get_by_text("1 immagine non ha il testo alternativo.")).to_be_visible()
    page.get_by_role("button", name="Aggiungilo ora").click()
    expect(page.get_by_label("Manca il testo alternativo")).to_be_checked()

    page.get_by_role("button", name=re.compile(r"lago\.png")).click()
    panel = page.get_by_role("complementary", name="lago.png")
    panel.get_by_label("Testo alternativo").fill("Il lago al mattino")
    panel.get_by_role("button", name="Salva", exact=True).click()
    expect(panel.get_by_text("Salvato.")).to_be_visible(timeout=WAIT_MS)

    marker = panel.get_by_role("slider", name="Punto da non tagliare")
    marker.focus()
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    expect(marker).to_have_attribute("aria-valuetext", "Orizzontale 60 %, verticale 50 %")
    panel.get_by_role("button", name="Salva punto").click()
    expect(panel.get_by_text("Salvato.")).to_be_visible(timeout=WAIT_MS)
    panel.get_by_role("button", name="Chiudi").click()

    page.get_by_label("Manca il testo alternativo").uncheck()
    page.get_by_role("button", name=re.compile(r"orari\.pdf")).click()
    pdf_panel = page.get_by_role("complementary", name="orari.pdf")
    pdf_panel.get_by_role("button", name="Elimina").click()
    page.get_by_role("dialog").get_by_role("button", name="Elimina").click()
    expect(page.get_by_text('"orari.pdf" è stato eliminato.')).to_be_visible(timeout=WAIT_MS)
    expect(page.get_by_role("button", name=re.compile(r"orari\.pdf"))).to_have_count(0)
