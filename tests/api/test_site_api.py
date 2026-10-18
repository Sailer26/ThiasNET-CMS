"""GET /api/admin/site: nome e indirizzo del sito per l'intestazione del pannello."""

from __future__ import annotations

import pytest
from flask.testing import FlaskClient

from tests.conftest import LoginAs

SITE = "/api/admin/site"


def test_site_requires_login(api: FlaskClient) -> None:
    assert api.get(SITE).status_code == 401


@pytest.mark.parametrize("role", ["owner", "admin", "editor"])
def test_every_role_reads_the_site(login_as: LoginAs, role: str) -> None:
    client, _ = login_as(role)
    data = client.get(SITE).get_json()["data"]
    assert data["url"] == "https://www.example.ch"
    assert data["name"]
    assert data["default_locale"] == data["locales"][0] == "it"
    assert (data["default_layout"], data["home_layout"]) == ("page", "home")
