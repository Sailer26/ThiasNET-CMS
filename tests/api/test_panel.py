"""Il pannello React servito da Flask su /admin/ (D-87, D-88)."""

from __future__ import annotations

from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app

INDEX = '<!doctype html><div id="root"></div><script type="module" src="/admin/assets/app-1.js"></script>'


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(INDEX, encoding="utf-8")
    (root / "assets" / "app-1.js").write_text("console.info(1)", encoding="utf-8")
    (root / "assets" / "app-1.css").write_text("body{}", encoding="utf-8")
    (root / "assets" / "nota.txt").write_text("no", encoding="utf-8")
    (tmp_path / "segreto.js").write_text("fuori", encoding="utf-8")
    return root


@pytest.fixture
def panel(dist: Path) -> FlaskClient:
    return create_app("testing", overrides={"ADMIN_DIST_DIR": dist}).test_client()


@pytest.mark.parametrize("path", ["/admin/", "/admin/pagine", "/admin/pagine/12", "/admin/cestino"])
def test_every_panel_address_gets_the_spa(panel: FlaskClient, path: str) -> None:
    response = panel.get(path)
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert 'id="root"' in response.get_data(as_text=True)


def test_panel_without_slash_redirects(panel: FlaskClient) -> None:
    response = panel.get("/admin")
    assert response.status_code == 308
    assert response.headers["Location"].endswith("/admin/")


def test_panel_page_is_locked_down(panel: FlaskClient) -> None:
    headers = panel.get("/admin/").headers
    csp = headers["Content-Security-Policy"]
    assert "script-src 'self';" in csp and "style-src 'self';" in csp
    assert "frame-ancestors 'none'" in csp and "frame-src 'self'" in csp
    assert "unsafe-inline" not in csp and "data:" not in csp and "unsafe-eval" not in csp
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "no-cache" in headers["Cache-Control"]
    assert "Set-Cookie" not in headers


def test_assets_are_served_immutable(panel: FlaskClient) -> None:
    response = panel.get("/admin/assets/app-1.js")
    assert response.status_code == 200
    assert "immutable" in response.headers["Cache-Control"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.mimetype == "text/javascript"
    assert panel.get("/admin/assets/app-1.css").mimetype == "text/css"


@pytest.mark.parametrize(
    "path",
    [
        "/admin/assets/manca.js",
        "/admin/assets/nota.txt",
        "/admin/assets/../segreto.js",
        "/admin/assets/%2e%2e/%2e%2e/segreto.js",
        "/admin/assets/..%5c..%5csegreto.js",
        "/admin/assets/",
        "/admin/assets/a%00.js",
    ],
)
def test_only_existing_build_files_are_served(panel: FlaskClient, path: str) -> None:
    response = panel.get(path)
    assert response.status_code == 404
    assert "fuori" not in response.get_data(as_text=True)


def test_symlinks_leaving_the_build_are_refused(panel: FlaskClient, dist: Path) -> None:
    link = dist / "assets" / "link.js"
    try:
        link.symlink_to(dist.parent / "segreto.js")
    except OSError:
        pytest.skip("collegamenti simbolici non disponibili")
    assert panel.get("/admin/assets/link.js").status_code == 404


def test_panel_routes_are_read_only(panel: FlaskClient) -> None:
    for method in (panel.post, panel.put, panel.delete):
        assert method("/admin/pagine").status_code == 405
        assert method("/admin/assets/app-1.js").status_code == 405


def test_missing_build_explains_what_to_do(tmp_path: Path) -> None:
    client = create_app("testing", overrides={"ADMIN_DIST_DIR": tmp_path / "vuota"}).test_client()
    response = client.get("/admin/pagine")
    assert response.status_code == 503
    assert "admin-build" in response.get_data(as_text=True)


def test_site_pages_starting_with_admin_stay_on_the_site(app: Flask) -> None:
    response = app.test_client().get("/admin-qualcosa")
    assert response.status_code == 404
    assert 'id="root"' not in response.get_data(as_text=True)
