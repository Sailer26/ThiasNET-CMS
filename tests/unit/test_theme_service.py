"""Il servizio tema espone il contratto in sola lettura (regola d'oro)."""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path
from typing import Any

import pytest

from app.services import theme as theme_module
from app.services.theme import Theme, ThemeValidationError, load_theme
from tests.conftest import ROOT, MakeTheme
from tests.unit.test_theme_schema import THUMBS, VARIANTS

WRITE_PREFIXES = ("write", "save", "update", "delete", "set", "create", "upload", "put", "remove")


@pytest.fixture
def theme() -> Theme:
    return load_theme(ROOT / "themes", "default")


@pytest.fixture
def variant_theme(make_theme: MakeTheme, theme_data: dict[str, Any]) -> Theme:
    theme_data["block_variants"] = VARIANTS
    return load_theme(make_theme(theme_data, thumbnails=THUMBS), "demo")


def test_layout_names(theme: Theme) -> None:
    assert set(theme.layouts) == {"home", "page", "full"}
    assert theme.layouts["page"].label == "Pagina standard"


def test_zones_for_layout(theme: Theme) -> None:
    assert theme.zones("page") == ("main", "sidebar")


def test_allowed_blocks_for_zone(theme: Theme) -> None:
    assert theme.allowed_blocks("home", "hero") == ("hero",)
    assert "text" in theme.allowed_blocks("page", "sidebar")
    assert "gallery" not in theme.allowed_blocks("page", "sidebar")


def test_zone_label_kept(make_theme: MakeTheme, theme_data: dict[str, Any]) -> None:
    theme_data["layouts"]["page"]["zones"]["sidebar"]["label"] = "Colonna"
    theme = load_theme(make_theme(theme_data), "demo")
    assert theme.layouts["page"].zones["sidebar"].label == "Colonna"
    assert theme.layouts["page"].zones["main"].label == "main"


def test_zone_max(theme: Theme) -> None:
    assert theme.zone_max("page", "sidebar") == 4
    assert theme.zone_max("page", "main") is None


def test_unknown_layout_raises(theme: Theme) -> None:
    with pytest.raises(KeyError):
        theme.zones("landing")


def test_unknown_zone_raises(theme: Theme) -> None:
    with pytest.raises(KeyError):
        theme.allowed_blocks("full", "sidebar")


def test_widget_areas(theme: Theme) -> None:
    assert "hours" in theme.widget_areas["footer"].widgets
    assert theme.widget_areas["footer"].label == "Piè di pagina"


def test_variants_for_and_default(variant_theme: Theme) -> None:
    variants = variant_theme.variants_for("text_image")
    assert variants is not None
    assert variants.default == "image_left"
    assert variants.options["dark"].label == "Sfondo scuro"
    assert variant_theme.variants_for("quote") is None


def test_is_valid_variant(variant_theme: Theme) -> None:
    assert variant_theme.is_valid_variant("text_image", "dark")
    assert not variant_theme.is_valid_variant("text_image", "neon")
    assert not variant_theme.is_valid_variant("text_image", None)
    assert variant_theme.is_valid_variant("quote", None)
    assert not variant_theme.is_valid_variant("quote", "dark")


def test_settings_exposed_typed(theme: Theme) -> None:
    accent = theme.setting("accent_color")
    assert accent.type == "color"
    assert accent.default == "#0B5FFF"
    assert "#1F7A4D" in accent.palette
    assert theme.setting("header_style").options == ("light", "dark")
    assert theme.setting("footer_note").max == 120
    with pytest.raises(KeyError):
        theme.setting("custom_css")


def test_collections_and_menus(theme: Theme) -> None:
    assert theme.collections["news"]["fields"]["date"]["type"] == "date"
    assert theme.menus["main"]["max_depth"] == 2
    assert theme.image_sizes["hero"]["width"] == 1920


def test_theme_model_is_immutable(theme: Theme) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        theme.name = "altro"  # type: ignore[misc]
    with pytest.raises(TypeError):
        theme.layouts["nuovo"] = theme.layouts["page"]  # type: ignore[index]
    with pytest.raises(TypeError):
        theme.collections["news"]["fields"]["x"] = {}
    assert isinstance(theme.locales, tuple)


def test_theme_service_has_no_write_api() -> None:
    names = [n for n in dir(theme_module) if not n.startswith("_")]
    names += [n for n in dir(Theme) if not n.startswith("_")]
    offenders = [
        n
        for n in names
        if any(n.lower() == p or n.lower().startswith(f"{p}_") for p in WRITE_PREFIXES)
    ]
    assert not offenders


def _dir_hash(path: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(path.rglob("*")):
        if p.is_file():
            h.update(p.as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def test_loading_does_not_modify_themes_dir(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    theme_data["block_variants"] = VARIANTS
    themes_dir = make_theme(theme_data, thumbnails=THUMBS)
    before = _dir_hash(themes_dir)
    load_theme(themes_dir, "demo")
    assert _dir_hash(themes_dir) == before


def test_error_type_is_value_error() -> None:
    assert issubclass(ThemeValidationError, ValueError)
