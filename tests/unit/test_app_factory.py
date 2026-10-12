from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app import create_app, get_theme
from app.config import ConfigError
from app.services.theme import ThemeValidationError
from tests.conftest import MakeTheme


def test_create_app_testing_loads_default_theme() -> None:
    app = create_app("testing")
    assert app.testing
    with app.app_context():
        assert get_theme().name == "default"


def test_create_app_fails_with_invalid_theme(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    theme_data["settings"]["custom_css"] = {"type": "text", "label": "CSS"}
    themes_dir = make_theme(theme_data)
    with pytest.raises(ThemeValidationError):
        create_app("testing", overrides={"THEMES_DIR": themes_dir, "ACTIVE_THEME": "demo"})


def test_create_app_fails_with_missing_theme(tmp_path: Path) -> None:
    with pytest.raises(ThemeValidationError):
        create_app("testing", overrides={"THEMES_DIR": tmp_path, "ACTIVE_THEME": "nessuno"})


def test_create_app_uses_app_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "testing")
    assert create_app().testing


def test_create_app_without_app_env_refuses_to_start() -> None:
    """Fail-closed: un deploy che dimentica APP_ENV non parte in modalità sviluppo."""
    with pytest.raises(ConfigError, match="APP_ENV"):
        create_app()


def test_get_theme_outside_app_context_raises() -> None:
    with pytest.raises(RuntimeError):
        get_theme()
