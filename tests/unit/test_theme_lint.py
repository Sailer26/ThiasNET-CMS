"""theme-check controlla anche i template del tema (D-63)."""

from __future__ import annotations

from typing import Any

from app.cli import check_all_themes
from app.services.theme import load_theme
from app.services.theme_lint import lint_theme
from tests.conftest import ROOT, MakeTheme


def test_default_theme_is_clean() -> None:
    assert lint_theme(load_theme(ROOT / "themes", "default")) == ([], [])


def _lint(
    make_theme: MakeTheme, theme_data: dict[str, Any], **changes: str | None
) -> tuple[list[str], list[str]]:
    themes_dir = make_theme(theme_data, templates=True)
    for relative, content in changes.items():
        target = themes_dir / "demo" / relative.replace("__", "/")
        if content is None:
            target.unlink()
        else:
            target.write_text(content, encoding="utf-8")
    return lint_theme(load_theme(themes_dir, "demo"))


def test_missing_templates_are_errors(make_theme: MakeTheme, theme_data: dict[str, Any]) -> None:
    errors, _ = _lint(
        make_theme, theme_data, **{"layouts__full.html": None, "blocks__quote.html": None}
    )
    assert any("layouts/full.html" in e for e in errors)
    assert any("blocks/quote.html" in e for e in errors)


def test_syntax_errors_are_reported_with_the_file(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    errors, _ = _lint(make_theme, theme_data, **{"blocks__text.html": "{% if %}"})
    assert any("blocks/text.html" in e for e in errors)


def test_cms_helpers_must_be_used(make_theme: MakeTheme, theme_data: dict[str, Any]) -> None:
    base = (ROOT / "themes" / "default" / "layouts" / "_base.html").read_text(encoding="utf-8")
    errors, _ = _lint(
        make_theme, theme_data, **{"layouts___base.html": base.replace("{{ cms_body_end() }}", "")}
    )
    assert any("cms_body_end" in e for e in errors)


def test_variants_of_blocks_never_allowed_are_warnings(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    for layout in theme_data["layouts"].values():
        for zone in layout["zones"].values():
            zone["blocks"] = [b for b in zone["blocks"] if b != "quote"]
    errors, warnings = _lint(make_theme, theme_data)
    assert errors == []
    assert any("quote" in w for w in warnings)


def test_check_all_themes_prints_template_problems(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    themes_dir = make_theme(theme_data, templates=True)
    (themes_dir / "demo" / "layouts" / "404.html").unlink()
    lines, failures = check_all_themes(themes_dir)
    assert failures == 1
    assert any(line.startswith("ERRORE") and "404.html" in line for line in lines)


def test_includes_of_missing_files_are_errors(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    errors, _ = _lint(
        make_theme, theme_data, **{"blocks__divider.html": "{% include 'partials/manca.html' %}"}
    )
    assert any("partials/manca.html" in e for e in errors)


def test_helper_names_in_comments_do_not_count(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    base = (ROOT / "themes" / "default" / "layouts" / "_base.html").read_text(encoding="utf-8")
    without = base.replace("{{ cms_head() }}", "{# cms_head() #}")
    errors, _ = _lint(make_theme, theme_data, **{"layouts___base.html": without})
    assert any("cms_head" in e for e in errors)
