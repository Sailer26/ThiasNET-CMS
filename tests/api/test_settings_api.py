"""Impostazioni del sito e dell'aspetto (Fase 6a, D-14, D-139, D-143)."""

from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import func, select

from app.extensions import db
from app.models.revision import EntityRevision
from tests.api.test_media_api import uploaded
from tests.conftest import LoginAs
from tests.helpers import API, error_code
from tests.media_fixtures import PDF_BYTES
from tests.pages_helpers import actions, create_page, doc, publish, put_draft, uid

SETTINGS = f"{API}/settings"


@pytest.fixture
def admin(login_as: LoginAs) -> FlaskClient:
    client, _ = login_as("admin")
    return client


def read(client: FlaskClient) -> dict[str, Any]:
    response = client.get(SETTINGS)
    assert response.status_code == 200, response.get_json()
    data: dict[str, Any] = response.get_json()["data"]
    return data


def put(client: FlaskClient, scope: str, values: dict[str, Any], version: int | None = None) -> Any:
    known = read(client)[scope]["version"] if version is None else version
    return client.put(f"{SETTINGS}/{scope}", json={"version": known, "values": values})


def details(response: Any) -> set[tuple[str, str]]:
    found = (response.get_json() or {}).get("error", {}).get("details") or []
    return {(d["path"], d["code"]) for d in found}


def test_only_admins_and_owner(login_as: LoginAs) -> None:
    editor, _ = login_as("editor")
    assert editor.get(SETTINGS).status_code == 403
    assert editor.put(f"{SETTINGS}/site", json={"version": 0, "values": {}}).status_code == 403


def test_read_has_schema_values_and_version(app: Flask, admin: FlaskClient) -> None:
    data = read(admin)
    site, look = data["site"], data["appearance"]
    assert site["version"] == 0 and look["version"] == 0
    # D-57: finché nessuno salva, il nome viene dalla configurazione
    assert site["values"]["name"] == app.config["SITE_NAME"]
    assert site["schema"]["properties"]["logo"]["x-media"] == "image"
    assert site["schema"]["properties"]["name"]["maxLength"] == 120
    for hidden in ("matomo_url", "site_url", "favicon"):  # D-143: restano di Thias
        assert hidden not in site["schema"]["properties"]
    color = look["schema"]["properties"]["accent_color"]
    assert color["x-color"] is True and "#0B5FFF" in color["enum"]
    assert look["schema"]["properties"]["header_style"]["enum"] == ["light", "dark"]
    assert look["values"]["accent_color"] == "#0B5FFF"  # il default di theme.json


def test_site_settings_are_saved_audited_and_used(app: Flask, admin: FlaskClient) -> None:
    logo = uploaded(admin, alt="Stemma del comune")
    values = {
        "name": "Comune di Prova",
        "logo": logo["id"],
        "email": "info@prova.ch",
        "phone": "+41 91 123 45 67",
        "address": "Piazza Grande 1\n6600 Locarno",
        "facebook": "https://www.facebook.com/prova",
        "contact_recipient": "messaggi@prova.ch",
    }
    response = put(admin, "site", values)
    assert response.status_code == 200, response.get_json()
    saved = response.get_json()["data"]
    assert saved["version"] == 1 and saved["values"]["name"] == "Comune di Prova"
    assert "settings.site_updated" in actions(app)
    with app.app_context():
        from app.services import site_settings

        current = site_settings.current()
        assert current.name == "Comune di Prova"
        assert current.contact_recipient == "messaggi@prova.ch"
        assert current.logo == logo["id"]
        count = db.session.execute(select(func.count()).select_from(EntityRevision)).scalar_one()
        assert count == 1
    # Il sito usa il nome nuovo (e la cache è stata invalidata)
    page = create_page(admin, "Home")
    assert publish(admin, page["id"]).status_code == 200
    html = admin.get("/").get_data(as_text=True)
    assert "Comune di Prova" in html


def test_version_conflict_says_who_saved(admin: FlaskClient) -> None:
    assert put(admin, "site", {"name": "Uno"}).status_code == 200
    response = put(admin, "site", {"name": "Due"}, version=0)
    assert (response.status_code, error_code(response)) == (409, "version_conflict")
    assert response.get_json()["error"]["details"]["updated_by_name"]


@pytest.mark.parametrize(
    ("values", "problem"),
    [
        ({"name": ""}, ("name", "required")),
        ({"name": "x" * 121}, ("name", "max_length")),
        ({"name": "Ok", "email": "non-una-email"}, ("email", "invalid_email")),
        ({"name": "Ok", "facebook": "http://facebook.com/x"}, ("facebook", "invalid_url")),
        ({"name": "Ok", "facebook": "javascript:alert(1)"}, ("facebook", "invalid_url")),
        ({"name": "Ok", "logo": 999999}, ("logo", "media_missing")),
        ({"name": "Ok", "logo": "1"}, ("logo", "invalid_type")),
        ({"name": "Ok", "logo": 10**20}, ("logo", "invalid_type")),  # SQLite non lo confronta
        ({"name": "Ok", "matomo_url": "https://stat.example.ch"}, ("matomo_url", "unknown")),
        ({"name": "Ok", "site_url": "https://altro.ch"}, ("site_url", "unknown")),
    ],
)
def test_site_validation(
    admin: FlaskClient, values: dict[str, Any], problem: tuple[str, str]
) -> None:
    response = put(admin, "site", values)
    assert response.status_code == 422
    assert problem in details(response)


def test_logo_must_be_an_image_and_counts_as_in_use(admin: FlaskClient) -> None:
    pdf = uploaded(admin, PDF_BYTES, "orari.pdf")
    response = put(admin, "site", {"name": "Ok", "logo": pdf["id"]})
    assert ("logo", "media_not_image") in details(response)
    logo = uploaded(admin, alt="Stemma")
    assert put(admin, "site", {"name": "Ok", "logo": logo["id"]}).status_code == 200
    detail = admin.get(f"{API}/media/{logo['id']}").get_json()["data"]
    assert {"where": "settings", "title": "Impostazioni del sito"}.items() <= detail["used_by"][
        0
    ].items()
    gone = admin.delete(f"{API}/media/{logo['id']}", json={"version": detail["version"]})
    assert (gone.status_code, error_code(gone)) == (409, "media_in_use")


@pytest.mark.parametrize(
    ("values", "problem"),
    [
        ({"accent_color": "#123456"}, ("accent_color", "not_in_palette")),
        ({"accent_color": "#fff;}body{display:none"}, ("accent_color", "invalid_color")),
        ({"accent_color": "</style>"}, ("accent_color", "invalid_color")),
        ({"show_breadcrumbs": "true"}, ("show_breadcrumbs", "invalid_type")),
        ({"header_style": "neon"}, ("header_style", "not_in_options")),
        ({"footer_note": "x" * 121}, ("footer_note", "max_length")),
        ({"custom_css": "body{}"}, ("custom_css", "unknown")),
        ({"accent_color": {"nested": "#0B5FFF"}}, ("accent_color", "invalid_type")),
    ],
)
def test_appearance_validation(
    admin: FlaskClient, values: dict[str, Any], problem: tuple[str, str]
) -> None:
    response = put(admin, "appearance", values)
    assert response.status_code == 422
    assert problem in details(response)


def test_appearance_reaches_css_and_templates_as_data(app: Flask, admin: FlaskClient) -> None:
    values = {
        "accent_color": "#1f7a4d",  # minuscolo: si normalizza
        "show_breadcrumbs": False,
        "header_style": "dark",
        "footer_note": "Aperti {{ 7*7 }} <b>giorni</b>",
    }
    response = put(admin, "appearance", values)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["data"]["values"]["accent_color"] == "#1F7A4D"
    assert "settings.appearance_updated" in actions(app)
    assert "--accent-color: #1F7A4D;" in admin.get("/_vars.css").get_data(as_text=True)
    page = create_page(admin, "Home")
    assert publish(admin, page["id"]).status_code == 200
    html = admin.get("/").get_data(as_text=True)
    assert "Aperti {{ 7*7 }} &lt;b&gt;giorni&lt;/b&gt;" in html  # testo, mai template né HTML
    assert "site-header--dark" in html


def test_stale_appearance_values_fall_back_to_the_default(app: Flask, admin: FlaskClient) -> None:
    """Dopo un cambio di tema i valori salvati che non vanno più bene valgono il default."""
    from app.models.settings import SettingsRow

    with app.app_context():
        db.session.add(
            SettingsRow(
                scope="appearance", values_json={"accent_color": "#ABCDEF", "gone": 1}, version=1
            )
        )
        db.session.commit()
        from app.services import site_settings
        from app.services.theme import active_theme

        values = site_settings.theme_settings(active_theme())
        assert values["accent_color"] == "#0B5FFF"
        assert "gone" not in values


def test_audit_diff_has_only_changed_keys(app: Flask, admin: FlaskClient) -> None:
    assert put(admin, "site", {"name": "Uno", "phone": "091 000 00 00"}).status_code == 200
    assert put(admin, "site", {"name": "Due", "phone": "091 000 00 00"}).status_code == 200
    from app.models.audit import AuditLog

    with app.app_context():
        last = (
            db.session.execute(
                select(AuditLog)
                .where(AuditLog.action == "settings.site_updated")
                .order_by(AuditLog.id.desc())
            )
            .scalars()
            .first()
        )
        assert last is not None and set((last.diff_json or {}).keys()) == {"name"}


def test_logo_usage_survives_page_usage(admin: FlaskClient) -> None:
    """Un'immagine usata sia da una pagina sia come logo compare due volte in "Usato in"."""
    logo = uploaded(admin, alt="Stemma")
    page = create_page(admin, "Chi siamo")
    image = {"uid": uid(1), "type": "image", "data": {"media_id": logo["id"]}}
    assert (
        put_draft(admin, page["id"], doc(zones={"main": [image], "sidebar": []})).status_code == 200
    )
    assert put(admin, "site", {"name": "Ok", "logo": logo["id"]}).status_code == 200
    used = admin.get(f"{API}/media/{logo['id']}").get_json()["data"]["used_by"]
    assert {u["where"] for u in used} == {"draft", "settings"}


def test_logo_needs_alt_text(admin: FlaskClient) -> None:
    bare = uploaded(admin)  # senza testo alternativo
    assert ("logo", "alt_missing") in details(
        put(admin, "site", {"name": "Ok", "logo": bare["id"]})
    )


def test_saved_by_someone_else_meanwhile_is_409(app: Flask, admin: FlaskClient) -> None:
    from app.models.settings import SettingsRow

    assert read(admin)["site"]["version"] == 0
    with app.app_context():  # un altro salva per primo
        db.session.add(SettingsRow(scope="site", values_json={"name": "Altro"}, version=1))
        db.session.commit()
    response = put(admin, "site", {"name": "Mio"}, version=0)
    assert (response.status_code, error_code(response)) == (409, "version_conflict")
    assert "queste impostazioni" in response.get_json()["error"]["message"]


def test_defaults_are_not_stored_and_a_cleared_field_goes_back(
    app: Flask, admin: FlaskClient
) -> None:
    """D-144: si salva solo ciò che differisce dal predefinito."""
    from app.models.settings import SettingsRow

    look = put(admin, "appearance", {"accent_color": "#0B5FFF", "header_style": "dark"})
    assert look.status_code == 200
    with app.app_context():
        row = db.session.get(SettingsRow, "appearance")
        assert row is not None and row.values_json == {"header_style": "dark"}
    assert put(admin, "site", {"name": "Ok", "contact_recipient": "a@prova.ch"}).status_code == 200
    cleared = put(admin, "site", {"name": "Ok"})
    assert cleared.get_json()["data"]["values"].get("contact_recipient") == app.config.get(
        "CONTACT_RECIPIENT"
    )


def test_old_recipient_is_told_when_the_address_changes(app: Flask, admin: FlaskClient) -> None:
    from app.services import mailer

    assert (
        put(admin, "site", {"name": "Ok", "contact_recipient": "vecchio@prova.ch"}).status_code
        == 200
    )
    before = len(app.extensions.get(mailer.OUTBOX_KEY, []))
    assert (
        put(admin, "site", {"name": "Ok", "contact_recipient": "nuovo@prova.ch"}).status_code == 200
    )
    sent = app.extensions.get(mailer.OUTBOX_KEY, [])[before:]
    assert [m["To"] for m in sent] == ["vecchio@prova.ch"]
    assert "nuovo@prova.ch" in sent[0].get_content()


def test_audit_does_not_keep_contact_details(app: Flask, admin: FlaskClient) -> None:
    from app.models.audit import AuditLog

    assert put(admin, "site", {"name": "Ok", "phone": "091 111 11 11"}).status_code == 200
    with app.app_context():
        last = (
            db.session.execute(
                select(AuditLog)
                .where(AuditLog.action == "settings.site_updated")
                .order_by(AuditLog.id.desc())
            )
            .scalars()
            .first()
        )
        assert last is not None and (last.diff_json or {})["phone"] == "(modificato)"
