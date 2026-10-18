"""Passi comuni degli e2e."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from tests.e2e.conftest import OWNER_EMAIL
from tests.helpers import PASSWORD

WAIT_MS = 15_000


def login(page: Page, base: str) -> None:
    page.goto(f"{base}/admin/")
    page.get_by_label("Email").fill(OWNER_EMAIL)
    page.get_by_label("Password").fill(PASSWORD)
    page.get_by_role("button", name="Accedi").click()
    expect(page.get_by_role("heading", name="Pagine")).to_be_visible()


def open_new_homepage(page: Page) -> None:
    page.get_by_role("button", name="Crea la homepage").click()
    page.get_by_role("dialog").get_by_role("button", name="Crea", exact=True).click()
    page.get_by_role("link", name="Home", exact=True).click()
    expect(page.get_by_label("Titolo della pagina")).to_have_value("Home")


def add_block(page: Page, zone: str, card: str) -> None:
    page.get_by_role("region", name=zone).get_by_role("button", name="Aggiungi blocco").click()
    page.get_by_role("dialog").get_by_role("button", name=re.compile(card)).click()
