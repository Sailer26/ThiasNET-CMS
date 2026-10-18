from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app import create_app
from app.cli import check_all_themes
from app.theme_check import main
from tests.conftest import MakeTheme


def test_standalone_check_works_when_active_theme_is_broken(
    make_theme: MakeTheme,
    theme_data: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Il comando serve proprio quando il tema attivo è rotto e l'app non parte."""
    theme_data["settings"]["custom_css"] = {"type": "text", "label": "CSS", "max": 10}
    themes_dir = make_theme(theme_data, name="rotto")
    monkeypatch.setenv("THEMES_DIR", str(themes_dir))
    monkeypatch.setenv("ACTIVE_THEME", "rotto")
    assert main() == 1
    output = capsys.readouterr().out
    assert "rotto" in output
    assert "custom_css" in output


def test_standalone_check_ok(make_theme: MakeTheme, theme_data: dict[str, Any]) -> None:
    lines, failures = check_all_themes(make_theme(theme_data, name="buono", templates=True))
    assert failures == 0
    assert any("buono" in line for line in lines)


def test_check_reports_directory_without_manifest(tmp_path: Path) -> None:
    (tmp_path / "vuoto").mkdir()
    (tmp_path / ".nascosto").mkdir()
    lines, failures = check_all_themes(tmp_path)
    assert failures == 1
    assert not any(".nascosto" in line for line in lines)


def test_check_missing_themes_dir(tmp_path: Path) -> None:
    lines, failures = check_all_themes(tmp_path / "manca")
    assert failures == 1
    assert "non esiste" in lines[0]


def test_theme_check_ok_on_repository_themes() -> None:
    app = create_app("testing")
    result = app.test_cli_runner().invoke(args=["theme-check"])
    assert result.exit_code == 0, result.output
    assert "default" in result.output


def test_theme_check_fails_on_invalid_theme(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    themes_dir = make_theme(theme_data, name="buono", templates=True)
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
    themes_dir = make_theme(theme_data, name="buono", templates=True)
    (themes_dir / "README.md").write_text("note", encoding="utf-8")
    app = create_app("testing", overrides={"THEMES_DIR": themes_dir, "ACTIVE_THEME": "buono"})
    result = app.test_cli_runner().invoke(args=["theme-check"])
    assert result.exit_code == 0, result.output
