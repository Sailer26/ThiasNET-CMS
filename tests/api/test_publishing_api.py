"""Pubblica, programma, ritira, revisioni e comando publish-scheduled (D-16, D-40, D-42, D-47)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import func, select, update

from app import ACTIVE_THEME_KEY
from app.extensions import db
from app.models.page import Block, Page, PageDraft, PageRevision
from app.services import publishing, revisions
from app.services.theme import load_theme
from tests.conftest import LoginAs, MakeTheme
from tests.helpers import error_code
from tests.pages_helpers import (
    PAGES,
    actions,
    create_page,
    details,
    doc,
    draft_version,
    get_draft,
    heading_block,
    page_version,
    publish,
    put_draft,
    restore,
    text_block,
    trash,
    uid,
)


@pytest.fixture
def admin(login_as: LoginAs) -> FlaskClient:
    client, _ = login_as("admin")
    return client


def _page_with_content(client: FlaskClient, title: str = "Chi siamo") -> dict[str, Any]:
    page = create_page(client, title)
    zones = {"main": [heading_block(1, "Benvenuti"), text_block(2)], "sidebar": [text_block(3)]}
    assert put_draft(client, page["id"], doc(title=title, zones=zones)).status_code == 200
    return page


def _schedule(client: FlaskClient, page_id: int, when: str) -> Any:
    return client.post(
        f"{PAGES}/{page_id}/schedule",
        json={"draft_version": draft_version(client, page_id), "publish_at": when},
    )


def _future(days: int = 1) -> datetime:
    return datetime.now(UTC) + timedelta(days=days)


def _stored(app: Flask, page_id: int) -> Page:
    with app.app_context():
        page = db.session.get_one(Page, page_id)
        db.session.expunge(page)
        return page


def _revision_kinds(app: Flask, page_id: int) -> list[str]:
    with app.app_context():
        query = select(PageRevision.kind).where(PageRevision.page_id == page_id)
        return list(db.session.execute(query.order_by(PageRevision.id)).scalars())


def _count(app: Flask, model: type, page_id: int) -> int:
    with app.app_context():
        query = select(func.count()).select_from(model).where(model.page_id == page_id)  # type: ignore[attr-defined]
        return db.session.execute(query).scalar_one()


# --- Permessi ------------------------------------------------------------------


def test_editor_needs_can_publish(login_as: LoginAs) -> None:
    editor, _ = login_as("editor")
    page = _page_with_content(editor)
    assert publish(editor, page["id"]).status_code == 403
    assert _schedule(editor, page["id"], _future().isoformat()).status_code == 403
    assert editor.post(f"{PAGES}/{page['id']}/unpublish", json={"version": 1}).status_code == 403
    publisher, _ = login_as("editor", can_publish=True)
    assert publish(publisher, page["id"]).status_code == 200


# --- Pubblica ------------------------------------------------------------------


def test_publish_replaces_blocks_and_records_revision(app: Flask, admin: FlaskClient) -> None:
    page = _page_with_content(admin, "Servizi")
    response = publish(admin, page["id"])
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert (data["status"], data["title"], data["has_draft"]) == ("published", "Servizi", False)
    assert data["published_at"] is not None
    assert data["version"] == page["version"] + 1
    with app.app_context():
        rows = db.session.execute(
            select(Block.zone, Block.uid, Block.sort)
            .where(Block.page_id == page["id"])
            .order_by(Block.zone, Block.sort)
        ).all()
    assert [tuple(r) for r in rows] == [
        ("main", uid(1), 0),
        ("main", uid(2), 1),
        ("sidebar", uid(3), 0),
    ]
    assert _count(app, PageDraft, page["id"]) == 0
    assert _revision_kinds(app, page["id"]) == ["published"]
    assert "page.published" in actions(app)

    # la seconda pubblicazione sostituisce i blocchi, non li accumula
    put_draft(
        admin,
        page["id"],
        doc(title="Servizi", zones={"main": [text_block(4)], "sidebar": []}),
        version=0,
    )
    assert publish(admin, page["id"]).status_code == 200
    with app.app_context():
        uids = (
            db.session.execute(select(Block.uid).where(Block.page_id == page["id"])).scalars().all()
        )
    assert uids == [uid(4)]


def test_publish_conflicts(admin: FlaskClient) -> None:
    page = _page_with_content(admin)
    stale = admin.post(f"{PAGES}/{page['id']}/publish", json={"draft_version": 1})
    assert (stale.status_code, error_code(stale)) == (409, "version_conflict")
    assert publish(admin, page["id"]).status_code == 200
    nothing = admin.post(f"{PAGES}/{page['id']}/publish", json={"draft_version": 0})
    assert (nothing.status_code, error_code(nothing)) == (409, "no_draft")


def test_publish_runs_full_validation(admin: FlaskClient) -> None:
    page = create_page(admin)
    put_draft(admin, page["id"], doc(title="", zones={"main": [text_block(1, "")], "sidebar": []}))
    response = publish(admin, page["id"])
    assert (response.status_code, error_code(response)) == (422, "invalid_content")
    assert details(response) == {("title", "required"), ("zones/main/0/data/body", "required")}


def test_theme_change_after_autosave_blocks_publishing(
    app: Flask, admin: FlaskClient, make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    page = _page_with_content(admin)
    del theme_data["layouts"]["page"]["zones"]["sidebar"]
    app.extensions[ACTIVE_THEME_KEY] = load_theme(make_theme(theme_data), "demo")
    response = publish(admin, page["id"])
    assert response.status_code == 422
    assert ("zones/sidebar", "unknown_zone") in details(response)


# --- Programma -------------------------------------------------------------------


@pytest.mark.parametrize(
    "when",
    [
        "2020-01-01T10:00:00+00:00",  # nel passato
        "2099-01-01T10:00",  # senza fuso
        "domani alle 10",
    ],
)
def test_schedule_rejects_bad_dates(admin: FlaskClient, when: str) -> None:
    page = _page_with_content(admin)
    response = _schedule(admin, page["id"], when)
    assert (response.status_code, error_code(response)) == (422, "invalid_publish_at")


def test_schedule_at_most_one_year_ahead(admin: FlaskClient) -> None:
    page = _page_with_content(admin)
    assert _schedule(admin, page["id"], _future(367).isoformat()).status_code == 422


def test_schedule_and_unschedule(app: Flask, admin: FlaskClient) -> None:
    page = _page_with_content(admin)
    when = (_future(2).astimezone(UTC) + timedelta(hours=2)).replace(microsecond=0)
    local = when.astimezone(timezone(timedelta(hours=2)))
    response = _schedule(admin, page["id"], local.isoformat())
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["status"] == "scheduled"
    assert datetime.fromisoformat(data["publish_at"]) == when
    assert data["publish_at"].endswith("+00:00")
    assert _revision_kinds(app, page["id"]) == ["scheduled"]
    assert get_draft(admin, page["id"])["version"] == 2  # la bozza resta modificabile

    again = _schedule(admin, page["id"], _future(3).isoformat())
    assert again.status_code == 200
    assert _revision_kinds(app, page["id"]) == ["scheduled"]  # sostituita, non duplicata

    cancel = admin.delete(
        f"{PAGES}/{page['id']}/schedule", json={"version": page_version(admin, page["id"])}
    )
    assert cancel.status_code == 200
    assert (cancel.get_json()["data"]["status"], cancel.get_json()["data"]["publish_at"]) == (
        "draft",
        None,
    )
    assert _revision_kinds(app, page["id"]) == []
    assert {"page.scheduled", "page.unscheduled"} <= set(actions(app))


def test_schedule_on_online_page_keeps_it_published(admin: FlaskClient) -> None:
    page = _page_with_content(admin)
    publish(admin, page["id"])
    put_draft(admin, page["id"], doc(zones={"main": [text_block(9)], "sidebar": []}), version=0)
    data = _schedule(admin, page["id"], _future().isoformat()).get_json()["data"]
    assert (data["status"], data["publish_at"] is not None) == ("published", True)


def test_publish_due_publishes_the_frozen_snapshot(app: Flask, admin: FlaskClient) -> None:
    due = _page_with_content(admin, "Scaduta")
    later = _page_with_content(admin, "Futura")
    _schedule(admin, due["id"], _future(1).isoformat())
    _schedule(admin, later["id"], _future(5).isoformat())
    # modifiche dopo la programmazione: non entrano nella pubblicazione programmata
    put_draft(
        admin, due["id"], doc(title="Scaduta", zones={"main": [text_block(7)], "sidebar": []})
    )

    with app.app_context():
        assert publishing.publish_due(_future(2)) == 1
        assert publishing.publish_due(_future(2)) == 0  # idempotente
    stored = _stored(app, due["id"])
    assert (stored.status, stored.publish_at) == ("published", None)
    assert _stored(app, later["id"]).status == "scheduled"
    with app.app_context():
        uids = (
            db.session.execute(select(Block.uid).where(Block.page_id == due["id"])).scalars().all()
        )
    assert sorted(uids) == [uid(1), uid(2), uid(3)]
    assert _revision_kinds(app, due["id"]) == ["published"]
    assert _count(app, PageDraft, due["id"]) == 1  # la bozza successiva resta


def test_publish_due_drops_a_draft_identical_to_the_snapshot(
    app: Flask, admin: FlaskClient
) -> None:
    page = _page_with_content(admin)
    _schedule(admin, page["id"], _future().isoformat())
    with app.app_context():
        publishing.publish_due(_future(2))
    assert _count(app, PageDraft, page["id"]) == 0


def test_publish_due_fails_safely_when_theme_changed(
    app: Flask, admin: FlaskClient, make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    page = _page_with_content(admin)
    _schedule(admin, page["id"], _future().isoformat())
    del theme_data["layouts"]["page"]["zones"]["sidebar"]
    app.extensions[ACTIVE_THEME_KEY] = load_theme(make_theme(theme_data), "demo")
    with app.app_context():
        assert publishing.publish_due(_future(2)) == 0
        assert publishing.publish_due(_future(2)) == 0  # niente tentativi a ripetizione
    stored = _stored(app, page["id"])
    assert (stored.status, stored.publish_at) == ("draft", None)
    assert _count(app, Block, page["id"]) == 0
    assert _revision_kinds(app, page["id"]) == ["draft"]  # l'istantanea resta recuperabile
    assert actions(app).count("page.schedule_failed") == 1


def test_publish_scheduled_cli(app: Flask, admin: FlaskClient) -> None:
    page = _page_with_content(admin)
    _schedule(admin, page["id"], _future().isoformat())
    with app.app_context():
        past = datetime.now(UTC) - timedelta(minutes=1)
        db.session.execute(update(Page).where(Page.id == page["id"]).values(publish_at=past))
        db.session.commit()
    result = app.test_cli_runner().invoke(args=["publish-scheduled"])
    assert result.exit_code == 0, result.output
    assert "1" in result.output
    assert _stored(app, page["id"]).status == "published"


def test_publish_now_cancels_pending_schedule(app: Flask, admin: FlaskClient) -> None:
    page = _page_with_content(admin)
    _schedule(admin, page["id"], _future().isoformat())
    assert publish(admin, page["id"]).status_code == 200
    assert _stored(app, page["id"]).publish_at is None
    assert _revision_kinds(app, page["id"]) == ["published"]


# --- Ritira ---------------------------------------------------------------------


def test_unpublish(app: Flask, admin: FlaskClient) -> None:
    page = _page_with_content(admin)
    publish(admin, page["id"])
    response = admin.post(
        f"{PAGES}/{page['id']}/unpublish", json={"version": page_version(admin, page["id"])}
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "draft"
    assert _revision_kinds(app, page["id"]) == ["published", "unpublished"]
    assert _count(app, Block, page["id"]) == 3  # il contenuto resta, solo non è più online
    assert "page.unpublished" in actions(app)
    again = admin.post(
        f"{PAGES}/{page['id']}/unpublish", json={"version": page_version(admin, page["id"])}
    )
    assert (again.status_code, error_code(again)) == (409, "not_published")


# --- Revisioni -------------------------------------------------------------------


def test_list_and_restore_revision_into_draft(app: Flask, admin: FlaskClient) -> None:
    page = _page_with_content(admin)
    publish(admin, page["id"])
    put_draft(admin, page["id"], doc(title="Seconda", zones={"main": [], "sidebar": []}), version=0)
    publish(admin, page["id"])
    put_draft(
        admin,
        page["id"],
        doc(title="Lavoro in corso", zones={"main": [], "sidebar": []}),
        version=0,
    )

    listing = admin.get(f"{PAGES}/{page['id']}/revisions").get_json()["data"]
    assert [r["kind"] for r in listing] == ["published", "published"]
    first = listing[-1]
    detail = admin.get(f"{PAGES}/{page['id']}/revisions/{first['id']}").get_json()["data"]
    assert detail["snapshot"]["title"] == "Chi siamo"

    response = admin.post(
        f"{PAGES}/{page['id']}/revisions/{first['id']}/restore", json={"draft_version": 1}
    )
    assert response.status_code == 200
    draft = get_draft(admin, page["id"])
    assert (draft["version"], draft["data"]["title"]) == (2, "Chi siamo")
    assert _stored(app, page["id"]).title == "Seconda"  # ripristinare non pubblica mai
    assert _revision_kinds(app, page["id"])[-1] == "draft"  # la bozza precedente è salvata
    assert "page.revision_restored" in actions(app)


def test_restore_checks_version_and_ownership(admin: FlaskClient) -> None:
    page = _page_with_content(admin)
    other = _page_with_content(admin, "Altra")
    publish(admin, page["id"])
    rid = admin.get(f"{PAGES}/{page['id']}/revisions").get_json()["data"][0]["id"]
    stale = admin.post(f"{PAGES}/{page['id']}/revisions/{rid}/restore", json={"draft_version": 5})
    assert stale.status_code == 409
    foreign = admin.post(
        f"{PAGES}/{other['id']}/revisions/{rid}/restore", json={"draft_version": 2}
    )
    assert foreign.status_code == 404
    assert admin.get(f"{PAGES}/{other['id']}/revisions/{rid}").status_code == 404


def test_revisions_are_pruned_to_fifty_keeping_the_schedule(app: Flask, admin: FlaskClient) -> None:
    page = _page_with_content(admin)
    with app.app_context():
        db.session.add_all(
            PageRevision(page_id=page["id"], kind="published", snapshot_json={}) for _ in range(60)
        )
        db.session.add(PageRevision(page_id=page["id"], kind="scheduled", snapshot_json={}))
        db.session.flush()
        revisions.prune(page["id"])
        db.session.commit()
    kinds = _revision_kinds(app, page["id"])
    assert len(kinds) == revisions.MAX_REVISIONS + 1
    assert kinds.count("scheduled") == 1


def test_trashing_a_scheduled_page_needs_publish_and_cancels_it(
    app: Flask, admin: FlaskClient, login_as: LoginAs
) -> None:
    editor, _ = login_as("editor")
    page = _page_with_content(admin)
    _schedule(admin, page["id"], _future().isoformat())
    assert trash(editor, page["id"]).status_code == 403
    assert trash(admin, page["id"]).status_code == 200
    stored = _stored(app, page["id"])
    assert (stored.status, stored.publish_at) == ("draft", None)
    with app.app_context():
        assert publishing.publish_due(_future(2)) == 0


# --- Catalogo dei blocchi --------------------------------------------------------------


def test_blocks_catalog_for_the_panel(admin: FlaskClient) -> None:
    body = admin.get("/api/admin/blocks").get_json()["data"]
    assert len(body["types"]) == 13
    assert body["types"]["hero"]["label"] == "Apertura"
    assert body["types"]["hero"]["schema"]["properties"]["title"]["maxLength"] == 120
    assert body["layouts"]["home"]["zones"]["hero"] == {
        "label": "hero",
        "blocks": ["hero"],
        "max": 1,
    }
    assert body["locales"] == ["it", "de", "rm", "en"]
    assert body["variants"]["text_image"]["default"] == "image_left"
    assert body["variants"]["cta"]["options"]["dark"] == {
        "label": "Scuro",
        "thumbnail": "variants/cta-dark.png",
    }


# --- Regressioni dalla review ECC della Fase 2 -------------------------------------------


def test_republish_after_unpublish_without_a_draft(admin: FlaskClient) -> None:
    page = _page_with_content(admin)
    publish(admin, page["id"])
    admin.post(f"{PAGES}/{page['id']}/unpublish", json={"version": page_version(admin, page["id"])})
    response = admin.post(f"{PAGES}/{page['id']}/publish", json={"draft_version": 0})
    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "published"


def test_republish_after_trash_and_restore(admin: FlaskClient) -> None:
    page = _page_with_content(admin)
    publish(admin, page["id"])
    assert trash(admin, page["id"]).status_code == 200
    assert restore(admin, page["id"]).status_code == 200
    assert publish(admin, page["id"]).status_code == 200


@pytest.mark.parametrize("when", ["9999-12-31T23:59:59-05:00", "0001-01-01T00:00:00+05:00"])
def test_extreme_dates_are_422_not_500(admin: FlaskClient, when: str) -> None:
    page = _page_with_content(admin)
    response = _schedule(admin, page["id"], when)
    assert (response.status_code, error_code(response)) == (422, "invalid_publish_at")


def test_one_failing_page_does_not_block_the_others(
    app: Flask, admin: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = _page_with_content(admin, "Prima"), _page_with_content(admin, "Seconda")
    _schedule(admin, first["id"], _future(1).isoformat())
    _schedule(admin, second["id"], _future(2).isoformat())
    real_apply = publishing._apply

    def broken(page: Page, *args: Any) -> None:
        if page.id == first["id"]:
            raise RuntimeError("errore del database simulato")
        real_apply(page, *args)

    monkeypatch.setattr(publishing, "_apply", broken)
    with app.app_context():
        result = publishing.run_due(_future(3))
    assert (result.published, result.failed) == (1, 1)
    assert _stored(app, second["id"]).status == "published"
    assert _stored(app, first["id"]).status == "scheduled"  # ritenta al prossimo giro
    with app.app_context():
        past = datetime.now(UTC) - timedelta(minutes=1)
        db.session.execute(update(Page).where(Page.id == first["id"]).values(publish_at=past))
        db.session.commit()
    assert app.test_cli_runner().invoke(args=["publish-scheduled"]).exit_code == 1


def test_scheduled_revision_is_dated_when_it_goes_online(app: Flask, admin: FlaskClient) -> None:
    page = _page_with_content(admin)
    _schedule(admin, page["id"], _future().isoformat())
    with app.app_context():
        old = datetime.now(UTC) - timedelta(days=1)
        db.session.add_all(
            PageRevision(page_id=page["id"], kind="draft", snapshot_json={}, created_at=old)
            for _ in range(revisions.MAX_REVISIONS + 5)
        )
        db.session.commit()
        moment = _future(2)
        assert publishing.publish_due(moment) == 1
        query = select(PageRevision).where(
            PageRevision.page_id == page["id"], PageRevision.kind == "published"
        )
        live = db.session.execute(query).scalar_one()  # non potata: è la più recente
        assert live.created_at == moment


def test_ensure_due_publishes_on_request(app: Flask, admin: FlaskClient) -> None:
    page = _page_with_content(admin)
    _schedule(admin, page["id"], _future().isoformat())
    with app.app_context():
        stored = db.session.get_one(Page, page["id"])
        assert publishing.ensure_due(stored, datetime.now(UTC)) is False
        assert publishing.ensure_due(stored, _future(2)) is True
    assert _stored(app, page["id"]).status == "published"


def test_schedule_without_snapshot_does_not_stay_scheduled(app: Flask, admin: FlaskClient) -> None:
    page = _page_with_content(admin)
    _schedule(admin, page["id"], _future().isoformat())
    with app.app_context():
        revisions.cancel_schedule(page["id"])
        db.session.commit()
        assert publishing.publish_due(_future(2)) == 0
    stored = _stored(app, page["id"])
    assert (stored.status, stored.publish_at) == ("draft", None)
