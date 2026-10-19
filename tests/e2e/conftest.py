"""Server vero per gli e2e (D-114): app di test con SQLite su file, CSRF attivo e il pannello
compilato. Si lancia con `python scripts/tasks.py e2e` (Edge su Windows, Chromium in CI)."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask
from werkzeug.serving import make_server

from app import create_app
from app.extensions import db
from app.services import users
from tests.helpers import PASSWORD

ROOT = Path(__file__).resolve().parents[2]
ADMIN_DIST = ROOT / "admin" / "dist"
OWNER_EMAIL = "e2e@thiasnet.test"


@pytest.fixture
def live_app(tmp_path: Path) -> Iterator[Flask]:
    """L'app del server e2e: serve anche a preparare dati che il pannello non crea (messaggi)."""
    if not (ADMIN_DIST / "index.html").is_file():
        pytest.fail("Manca la build del pannello: esegui python scripts/tasks.py admin-build")
    app = create_app(
        "testing",
        overrides={
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'e2e.db').as_posix()}",
            "ADMIN_DIST_DIR": ADMIN_DIST,
            "MEDIA_ROOT": tmp_path / "media",  # i file caricati non finiscono nel progetto
        },
    )
    with app.app_context():
        db.create_all()  # ammesso nei test (CLAUDE.md)
        users.create_owner(OWNER_EMAIL, PASSWORD)
    try:
        yield app
    finally:
        with app.app_context():
            db.engine.dispose()


@pytest.fixture
def live_server(live_app: Flask) -> Iterator[str]:
    server = make_server("127.0.0.1", 0, live_app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
