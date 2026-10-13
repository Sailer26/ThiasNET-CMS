from __future__ import annotations

from flask import Flask
from sqlalchemy import select

from app.extensions import db
from app.models.audit import AuditLog
from app.services import audit


def test_record_redacts_sensitive_keys(app: Flask) -> None:
    with app.test_request_context(environ_base={"REMOTE_ADDR": "203.0.113.10"}):
        audit.record(
            "user.updated",
            actor_id=None,
            entity="user",
            entity_id=7,
            diff={
                "role": ["editor", "admin"],
                "password": "segreta",
                "nested": {"totp_secret": "x", "ok": 1},
                "password_hash": "h",
                "token": "t",
            },
        )
        db.session.commit()
        entry = db.session.execute(select(AuditLog)).scalar_one()
        assert entry.diff_json == {"role": ["editor", "admin"], "nested": {"ok": 1}}
        assert entry.entity_id == "7"
        assert entry.ip_hash is not None
        assert len(entry.ip_hash) == 64
        assert "203.0.113.10" not in entry.ip_hash
        assert entry.created_at.tzinfo is not None


def test_record_without_request_has_no_ip(app: Flask) -> None:
    with app.app_context():
        audit.record("system.test", actor_id=None)
        db.session.commit()
        assert db.session.execute(select(AuditLog)).scalar_one().ip_hash is None


def test_list_entries_newest_first(app: Flask) -> None:
    with app.app_context():
        for action in ("a", "b", "c"):
            audit.record(action, actor_id=None)
        db.session.commit()
        entries, total = audit.list_entries(page=1, limit=2)
        assert total == 3
        assert [e.action for e in entries] == ["c", "b"]
