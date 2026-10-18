"""Aiuti per i test delle pagine: creazione, bozze e pubblicazione via API come farà la SPA."""

from __future__ import annotations

from typing import Any

from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import select
from werkzeug.test import TestResponse

from app.extensions import db
from app.models.audit import AuditLog
from tests.helpers import API

PAGES = f"{API}/pages"


def uid(n: int) -> str:
    """uid stabile di un blocco (D-39): 32 caratteri esadecimali."""
    return f"{n:032x}"


def text_block(n: int, body: str = "<p>Testo</p>", **extra: Any) -> dict[str, Any]:
    return {"uid": uid(n), "type": "text", "data": {"body": body}, **extra}


def heading_block(n: int, text: str = "Titolo") -> dict[str, Any]:
    return {"uid": uid(n), "type": "heading", "data": {"text": text}}


def doc(
    title: str = "Chi siamo",
    layout: str = "page",
    zones: dict[str, list[dict[str, Any]]] | None = None,
    seo: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "title": title,
        "layout": layout,
        "seo": seo or {},
        "zones": zones if zones is not None else {"main": [], "sidebar": []},
    }


def create_page(client: FlaskClient, title: str = "Chi siamo", **extra: Any) -> dict[str, Any]:
    response = client.post(PAGES, json={"title": title, "layout": "page", **extra})
    assert response.status_code == 201, response.get_json()
    data: dict[str, Any] = response.get_json()["data"]
    return data


def get_draft(client: FlaskClient, page_id: int) -> dict[str, Any]:
    response = client.get(f"{PAGES}/{page_id}/draft")
    assert response.status_code == 200, response.get_json()
    data: dict[str, Any] = response.get_json()["data"]
    return data


def draft_version(client: FlaskClient, page_id: int) -> int:
    version: int = get_draft(client, page_id)["version"]
    return version


def put_draft(
    client: FlaskClient, page_id: int, body: dict[str, Any], version: int | None = None
) -> TestResponse:
    known = draft_version(client, page_id) if version is None else version
    return client.put(f"{PAGES}/{page_id}/draft", json={"version": known, **body})


def publish(client: FlaskClient, page_id: int) -> TestResponse:
    return client.post(
        f"{PAGES}/{page_id}/publish", json={"draft_version": draft_version(client, page_id)}
    )


def page_version(client: FlaskClient, page_id: int) -> int:
    version: int = client.get(f"{PAGES}/{page_id}").get_json()["data"]["version"]
    return version


def trash(client: FlaskClient, page_id: int, version: int | None = None) -> TestResponse:
    known = page_version(client, page_id) if version is None else version
    return client.delete(f"{PAGES}/{page_id}", json={"version": known})


def restore(client: FlaskClient, page_id: int) -> TestResponse:
    """Ripristina dal cestino con la versione mostrata nell'elenco del cestino."""
    trashed = client.get(f"{PAGES}/trash?limit=100").get_json()["data"]
    version = next(p["version"] for p in trashed if p["id"] == page_id)
    return client.post(f"{PAGES}/{page_id}/restore", json={"version": version})


def actions(app: Flask) -> list[str]:
    with app.app_context():
        return list(db.session.execute(select(AuditLog.action).order_by(AuditLog.id)).scalars())


def details(response: TestResponse) -> set[tuple[str, str]]:
    """(percorso, codice) degli errori di validazione restituiti in `error.details`."""
    found = (response.get_json() or {}).get("error", {}).get("details") or []
    return {(d["path"], d["code"]) for d in found}
