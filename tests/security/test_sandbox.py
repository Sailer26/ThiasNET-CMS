"""Il motore dei template è protetto (D-52): né i contenuti né un tema sbagliato eseguono codice."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from jinja2.exceptions import SecurityError, TemplateNotFound
from jinja2.sandbox import ImmutableSandboxedEnvironment

from app.services.render import build_environment
from app.services.theme import Theme, load_theme
from tests.conftest import ROOT, MakeTheme
from tests.pages_helpers import doc, text_block
from tests.render_fixtures import render_doc


def _theme_with_layout(make_theme: MakeTheme, theme_data: dict[str, Any], source: str) -> Theme:
    themes_dir = make_theme(theme_data)
    layouts = themes_dir / "demo" / "layouts"
    layouts.mkdir()
    (layouts / "page.html").write_text(source, encoding="utf-8")
    return load_theme(themes_dir, "demo")


def test_environment_is_sandboxed_and_limited_to_the_theme() -> None:
    theme_dir = ROOT / "themes" / "default"
    env = build_environment(theme_dir)
    assert isinstance(env, ImmutableSandboxedEnvironment)
    assert env.autoescape is True
    assert env.loader is not None
    assert list(env.loader.searchpath) == [str(theme_dir)]  # type: ignore[attr-defined]
    assert env.loader.followlinks is False  # type: ignore[attr-defined]
    assert not {"config", "request", "session", "url_for", "g"} & set(env.globals)


@pytest.mark.parametrize(
    "content",
    ["{{ config }}", "{{ ''.__class__.__mro__ }}", "{% for x in range(3) %}{{ x }}{% endfor %}"],
)
def test_template_syntax_in_content_stays_text(content: str) -> None:
    theme = load_theme(ROOT / "themes", "default")
    html = render_doc(
        theme, doc(title=content, zones={"main": [text_block(1, f"<p>{content}</p>")]})
    )
    assert "SECRET" not in html and "<class" not in html and "012" not in html


def test_malicious_theme_template_cannot_reach_python_internals(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    theme = _theme_with_layout(
        make_theme, theme_data, "{{ ''.__class__.__mro__[1].__subclasses__() }}"
    )
    with pytest.raises(SecurityError):
        render_doc(theme, doc())


def test_theme_cannot_include_files_outside_its_folder(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    theme = _theme_with_layout(make_theme, theme_data, "{% include '../../../app/config.py' %}")
    with pytest.raises(TemplateNotFound):
        render_doc(theme, doc())


def test_symlinks_leaving_the_theme_are_not_followed(
    make_theme: MakeTheme, theme_data: dict[str, Any], tmp_path: Path
) -> None:
    secret = tmp_path / "segreto.html"
    secret.write_text("SEGRETO", encoding="utf-8")
    theme = _theme_with_layout(make_theme, theme_data, "{% include 'partials/link.html' %}")
    partials = theme.directory / "partials"
    partials.mkdir()
    try:
        (partials / "link.html").symlink_to(secret)
    except OSError:
        pytest.skip("symlink non consentiti su questo sistema")
    with pytest.raises(TemplateNotFound):
        render_doc(theme, doc())
