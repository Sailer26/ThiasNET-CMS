from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from flask import Flask
from sqlalchemy import func, select

from app import create_app
from app.extensions import db
from app.models.login_attempt import LoginAttempt
from app.services import rate_limit


def test_blocks_after_max_failures_per_email_ip(app: Flask) -> None:
    with app.app_context():
        for _ in range(rate_limit.MAX_PER_EMAIL_IP):
            assert rate_limit.retry_after("a@example.ch", "1.1.1.1") is None
            rate_limit.register_failure("a@example.ch", "1.1.1.1")
        wait = rate_limit.retry_after("a@example.ch", "1.1.1.1")
        assert wait is not None
        assert 0 < wait <= rate_limit.WINDOW.total_seconds()
        # stessa email da un altro IP: nessun blocco (niente DoS sull'account)
        assert rate_limit.retry_after("a@example.ch", "2.2.2.2") is None


def test_ipv6_addresses_in_same_64_share_the_limit(app: Flask) -> None:
    """Con IPv6 ognuno ha miliardi di indirizzi: si conta per rete /64."""
    with app.app_context():
        for i in range(rate_limit.MAX_PER_EMAIL_IP):
            rate_limit.register_failure("a@example.ch", f"2001:db8:1:2::{i + 1}")
        assert rate_limit.retry_after("a@example.ch", "2001:db8:1:2:ffff::9") is not None
        assert rate_limit.retry_after("a@example.ch", "2001:db8:1:3::1") is None


def test_email_is_case_insensitive(app: Flask) -> None:
    with app.app_context():
        for _ in range(rate_limit.MAX_PER_EMAIL_IP):
            rate_limit.register_failure("A@Example.CH", "1.1.1.1")
        assert rate_limit.retry_after("a@example.ch", "1.1.1.1") is not None


def test_blocks_ip_across_emails(app: Flask) -> None:
    with app.app_context():
        for i in range(rate_limit.MAX_PER_IP):
            rate_limit.register_failure(f"u{i}@example.ch", "1.1.1.1")
        assert rate_limit.retry_after("nuovo@example.ch", "1.1.1.1") is not None


def test_clear_resets_email_counter(app: Flask) -> None:
    with app.app_context():
        for _ in range(rate_limit.MAX_PER_EMAIL_IP):
            rate_limit.register_failure("a@example.ch", "1.1.1.1")
        rate_limit.clear("a@example.ch", "1.1.1.1")
        assert rate_limit.retry_after("a@example.ch", "1.1.1.1") is None


def test_old_attempts_expire_and_are_purged(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    with app.app_context():
        for _ in range(rate_limit.MAX_PER_EMAIL_IP):
            rate_limit.register_failure("a@example.ch", "1.1.1.1")
        later = datetime.now(UTC) + rate_limit.RETENTION + timedelta(minutes=1)
        monkeypatch.setattr(rate_limit, "_now", lambda: later)
        assert rate_limit.retry_after("a@example.ch", "1.1.1.1") is None
        rate_limit.register_failure("b@example.ch", "1.1.1.1")
        count = db.session.execute(select(func.count()).select_from(LoginAttempt)).scalar_one()
        assert count == 1


def test_stored_keys_do_not_contain_email_or_ip(app: Flask) -> None:
    with app.app_context():
        rate_limit.register_failure("a@example.ch", "1.1.1.1")
        row = db.session.execute(select(LoginAttempt)).scalar_one()
        assert "example" not in row.email_key
        assert "1.1.1.1" not in row.ip_key


def test_shared_between_app_instances(tmp_path: Path) -> None:
    """Più worker gunicorn = più istanze dell'app sullo stesso database."""
    uri = f"sqlite:///{(tmp_path / 'cms.db').as_posix()}"
    first = create_app("testing", overrides={"SQLALCHEMY_DATABASE_URI": uri})
    second = create_app("testing", overrides={"SQLALCHEMY_DATABASE_URI": uri})
    with first.app_context():
        db.create_all()
        for _ in range(rate_limit.MAX_PER_EMAIL_IP):
            rate_limit.register_failure("a@example.ch", "1.1.1.1")
    with second.app_context():
        assert rate_limit.retry_after("a@example.ch", "1.1.1.1") is not None
