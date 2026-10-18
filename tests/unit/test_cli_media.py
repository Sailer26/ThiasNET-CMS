"""`flask media-variants` crea le varianti mancanti dopo un cambio di image_sizes (D-73)."""

from __future__ import annotations

from typing import Any

from flask import Flask

from app import ACTIVE_THEME_KEY
from app.services.theme import load_theme
from tests.api.test_media_api import uploaded
from tests.conftest import LoginAs, MakeTheme
from tests.media_fixtures import PDF_BYTES


def test_missing_variants_are_created(
    app: Flask, login_as: LoginAs, make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    admin, _ = login_as("admin")
    media = uploaded(admin)
    uploaded(admin, PDF_BYTES, "orari.pdf")  # i PDF non hanno varianti
    theme_data["image_sizes"]["banner"] = {"width": 600, "ratio": "3:1"}
    app.extensions[ACTIVE_THEME_KEY] = load_theme(make_theme(theme_data), "demo")

    dry = app.test_cli_runner().invoke(args=["media-variants", "--dry-run"])
    assert dry.exit_code == 0 and "1" in dry.output
    result = app.test_cli_runner().invoke(args=["media-variants"])
    assert result.exit_code == 0, result.output
    detail = admin.get(f"/api/admin/media/{media['id']}").get_json()["data"]
    assert "banner" in detail["sizes"] and detail["file_rev"] == 2
    again = app.test_cli_runner().invoke(args=["media-variants"])
    assert "0" in again.output  # idempotente
