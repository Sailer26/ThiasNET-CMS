"""Amministrazione nel browser (5c-2): messaggio letto, nuovo editor con password generata,
registro, profilo; l'editor appena creato non vede le sezioni riservate."""

from __future__ import annotations

import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from app.extensions import db
from app.models.contact import ContactMessage
from tests.e2e.helpers import WAIT_MS, login

pytestmark = pytest.mark.e2e

EDITOR_EMAIL = "redazione@thiasnet.test"


def _seed_message(app: Flask) -> None:
    with app.app_context():
        db.session.add(
            ContactMessage(
                block_uid="a" * 32,
                locale="it",
                name="Mario Rossi",
                email="mario@thiasnet.test",
                message="Vorrei sapere gli orari dello sportello.",
                ip_hash="h" * 64,
            )
        )
        db.session.commit()


def test_messages_users_audit_profile(page: Page, live_app: Flask, live_server: str) -> None:
    _seed_message(live_app)
    login(page, live_server)
    nav = page.get_by_role("navigation", name="Menu del pannello")

    # Messaggi: il numero nel menu, letto all'apertura
    expect(nav.get_by_role("link", name=re.compile("Messaggi.*1 da leggere"))).to_be_visible(
        timeout=WAIT_MS
    )
    nav.get_by_role("link", name=re.compile("Messaggi")).click()
    page.get_by_role("link", name=re.compile("Mario Rossi")).click()
    expect(page.get_by_role("heading", name="Mario Rossi")).to_be_visible()
    expect(page.get_by_text("Vorrei sapere gli orari dello sportello.")).to_be_visible()
    expect(page.get_by_role("link", name="Rispondi")).to_have_attribute(
        "href", re.compile("^mailto:")
    )
    expect(nav.get_by_role("link", name="Messaggi", exact=True)).to_be_visible(timeout=WAIT_MS)

    # Utenti: nuovo editor con la password generata
    nav.get_by_role("link", name="Utenti").click()
    page.get_by_role("button", name="Nuovo utente").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Email").fill(EDITOR_EMAIL)
    password = dialog.get_by_label("Password iniziale").input_value()
    assert len(password) == 16
    dialog.get_by_role("button", name="Crea").click()
    expect(page.get_by_text(f"Utente {EDITOR_EMAIL} creato.")).to_be_visible()

    # Registro: la creazione è registrata
    nav.get_by_role("link", name="Registro").click()
    page.get_by_label("Tipo").select_option("users")
    # due righe: ThiasNET (creato all'avvio) e il nuovo editor
    expect(page.get_by_text("Utente creato")).to_have_count(2, timeout=WAIT_MS)

    # Profilo dall'email in alto
    page.get_by_role("link", name="e2e@thiasnet.test").click()
    expect(page.get_by_role("heading", name="Il tuo profilo")).to_be_visible()
    page.get_by_role("button", name="Esci", exact=True).click()

    # L'editor appena creato entra e non vede le sezioni riservate
    page.get_by_label("Email").fill(EDITOR_EMAIL)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Accedi").click()
    # si resta sull'indirizzo di prima: ora è il profilo dell'editor
    expect(page.get_by_role("heading", name="Il tuo profilo")).to_be_visible()
    expect(page.get_by_text(EDITOR_EMAIL).first).to_be_visible()
    expect(nav.get_by_role("link", name=re.compile("Messaggi"))).to_have_count(0)
    expect(nav.get_by_role("link", name="Utenti")).to_have_count(0)
    page.goto(f"{live_server}/admin/registro")
    expect(page.get_by_role("heading", name="Non hai accesso a questa sezione.")).to_be_visible()
