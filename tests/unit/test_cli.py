from __future__ import annotations

from typing import Any

from app import create_app
from tests.conftest import MakeTheme


def test_theme_check_ok_on_repository_themes() -> None:
    app = create_app("testing")
    result = app.test_cli_runner().invoke(args=["theme-check"])
    assert result.exit_code == 0, result.output
    assert "default" in result.output


def test_theme_check_fails_on_invalid_theme(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    themes_dir = make_theme(theme_data, name="buono")
    theme_data["settings"]["custom_css"] = {"type": "text", "label": "CSS"}
    make_theme(theme_data, name="rotto")
    app = create_app("testing", overrides={"THEMES_DIR": themes_dir, "ACTIVE_THEME": "buono"})
    result = app.test_cli_runner().invoke(args=["theme-check"])
    assert result.exit_code == 1
    assert "rotto" in result.output
    assert "custom_css" in result.output


def test_theme_check_ignores_files_in_themes_dir(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    themes_dir = make_theme(theme_data, name="buono")
    (themes_dir / "README.md").write_text("note", encoding="utf-8")
    app = create_app("testing", overrides={"THEMES_DIR": themes_dir, "ACTIVE_THEME": "buono"})
    result = app.test_cli_runner().invoke(args=["theme-check"])
    assert result.exit_code == 0, result.output
