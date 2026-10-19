"""Trascinamento dei blocchi da tastiera nel browser vero (D-109)."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.helpers import WAIT_MS, add_block, login, open_new_homepage

pytestmark = pytest.mark.e2e
ARROW_TRIES = 3
ARROW_WAIT_MS = 2_000


def test_keyboard_drag_reorders_blocks(page: Page, live_server: str) -> None:
    login(page, live_server)
    open_new_homepage(page)
    zone = page.get_by_role("region", name="Contenuto principale")
    add_block(page, "Contenuto principale", r"^Titolo Un titolo")
    add_block(page, "Contenuto principale", r"^Separatore")
    titles = zone.locator(".block-row__title strong")
    expect(titles).to_have_text(["Titolo", "Separatore"])

    zone.get_by_role("button", name=re.compile(r'Trascina per spostare il blocco "Titolo"')).focus()
    # Come una persona: si aspetta l'annuncio di ogni passo (dnd-kit misura le posizioni).
    page.keyboard.press("Space")
    expect(page.get_by_text("Il blocco Titolo è sulla posizione 1.")).to_be_attached(
        timeout=WAIT_MS
    )
    # Se la freccia arriva prima che le posizioni siano misurate, si ripete.
    moved = page.get_by_text("Il blocco Titolo è sulla posizione 2.")
    for _ in range(ARROW_TRIES):
        page.keyboard.press("ArrowDown")
        try:
            expect(moved).to_be_attached(timeout=ARROW_WAIT_MS)
            break
        except AssertionError:
            continue
    expect(moved).to_be_attached(timeout=WAIT_MS)
    page.keyboard.press("Space")
    expect(titles).to_have_text(["Separatore", "Titolo"], timeout=WAIT_MS)
    expect(page.get_by_text(re.compile(r"^Salvato alle"))).to_be_visible(timeout=WAIT_MS)
