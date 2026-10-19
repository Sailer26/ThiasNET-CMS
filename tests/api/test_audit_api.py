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
    for query in (
        "since=ieri",
        "user_id=x",
        "user_id=%C2%B2",  # "²": isdigit() vero, int() no
        "user_id=99999999999999999999",
        "category=tutto",
        "entity=page",
        "until=2026-13-40",
        "until=9999-12-31",  # il giorno dopo non esiste
        "since=2026-10-19T00:00:00",  # un istante senza fuso è ambiguo
    ):
        assert owner.get(f"{AUDIT}?{query}").status_code == 422, query


def test_instants_with_offset_bound_the_swiss_day(app: Flask, login_as: LoginAs) -> None:
    """Il pannello manda la mezzanotte di Zurigo (D-124): fine esclusa."""
    from datetime import UTC, datetime

    from app.extensions import db
    from app.models.audit import AuditLog

    owner, _ = login_as("owner")
    with app.app_context():
        # 19 ottobre 00:30 a Zurigo = 18 ottobre 22:30 UTC
        db.session.add(
            AuditLog(action="page.created", created_at=datetime(2026, 10, 18, 22, 30, tzinfo=UTC))
        )
        db.session.commit()

    def count(query: str) -> int:
        rows = owner.get(f"{AUDIT}?category=pages&{query}").get_json()["data"]
        return len([r for r in rows if r["created_at"].startswith("2026-10-18T22:30")])

    day = "since=2026-10-19T00:00:00%2B02:00&until=2026-10-20T00:00:00%2B02:00"
    assert count(day) == 1
    assert count("since=2026-10-18T00:00:00%2B02:00&until=2026-10-19T00:00:00%2B02:00") == 0
