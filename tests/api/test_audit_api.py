"""Registro attività (5c-2, D-124): solo owner, filtri, nomi leggibili."""

from __future__ import annotations

from flask import Flask

from tests.conftest import LoginAs
from tests.helpers import API
from tests.pages_helpers import create_page

AUDIT = f"{API}/audit"


def test_only_owner(login_as: LoginAs) -> None:
    admin, _ = login_as("admin")
    assert admin.get(AUDIT).status_code == 403


def test_filters_and_labels(app: Flask, login_as: LoginAs) -> None:
    owner, _ = login_as("owner")
    admin, admin_user = login_as("admin")
    page = create_page(admin, "Chi siamo")
    entries = owner.get(AUDIT).get_json()["data"]
    created = next(e for e in entries if e["action"] == "page.created")
    assert created["actor_email"] == admin_user.email
    assert created["entity_label"] == "Chi siamo"

    by_admin = owner.get(f"{AUDIT}?user_id={admin_user.id}").get_json()["data"]
    assert by_admin and {e["user_id"] for e in by_admin} == {admin_user.id}
    pages = owner.get(f"{AUDIT}?category=pages").get_json()["data"]
    assert pages and all(e["action"].startswith("page.") for e in pages)
    access = owner.get(f"{AUDIT}?category=access").get_json()["data"]
    assert access and all(e["action"].startswith("auth.") for e in access)
    one = owner.get(f"{AUDIT}?entity=page&entity_id={page['id']}").get_json()["data"]
    assert one and {e["entity_id"] for e in one} == {str(page["id"])}
    assert owner.get(f"{AUDIT}?since=2099-01-01").get_json()["data"] == []
    assert owner.get(f"{AUDIT}?until=2000-01-01").get_json()["data"] == []


def test_bad_filters_are_422(login_as: LoginAs) -> None:
    owner, _ = login_as("owner")
    for query in ("since=ieri", "user_id=x", "category=tutto", "entity=page", "until=2026-13-40"):
        assert owner.get(f"{AUDIT}?{query}").status_code == 422, query
