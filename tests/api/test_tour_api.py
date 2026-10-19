"""Tour al primo accesso (5d-2, D-133): si segna una volta sola, per ogni ruolo."""

from __future__ import annotations

import pytest
from flask import Flask

from tests.conftest import LoginAs
from tests.helpers import API, api_client

TOUR = f"{API}/auth/me/tour"


@pytest.mark.parametrize("role", ["owner", "admin", "editor"])
def test_finishing_the_tour_is_remembered(login_as: LoginAs, role: str) -> None:
    client, _ = login_as(role)
    assert client.get(f"{API}/auth/me").get_json()["data"]["tour_completed_at"] is None
    response = client.post(TOUR)
    assert response.status_code == 200, response.get_json()
    first = response.get_json()["data"]["tour_completed_at"]
    assert first is not None
    assert client.get(f"{API}/auth/me").get_json()["data"]["tour_completed_at"] == first


def test_doing_it_again_keeps_the_first_date(login_as: LoginAs) -> None:
    client, _ = login_as("editor")
    first = client.post(TOUR).get_json()["data"]["tour_completed_at"]
    assert client.post(TOUR).get_json()["data"]["tour_completed_at"] == first


def test_anonymous_cannot_mark_the_tour(app: Flask) -> None:
    assert api_client(app).post(TOUR).status_code in {401, 403}
