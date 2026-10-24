"""Validazione di theme.json: ogni errore blocca l'avvio con un messaggio che indica il campo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.services.theme import ThemeValidationError, load_theme
from tests.conftest import FAKE_IMAGES, ROOT, MakeTheme

VARIANTS: dict[str, Any] = {
    "text_image": {
        "default": "image_left",
        "options": {
            "image_left": {"label": "Immagine a sinistra", "thumbnail": "variants/ti-left.webp"},
            "dark": {"label": "Sfondo scuro", "thumbnail": "variants/ti-dark.webp"},
        },
    }
}
THUMBS = ("variants/ti-left.webp", "variants/ti-dark.webp")


def _expect_error(make_theme: MakeTheme, data: dict[str, Any] | str, match: str, **kw: Any) -> None:
    themes_dir = make_theme(data, **kw)
    with pytest.raises(ThemeValidationError, match=match):
        load_theme(themes_dir, "demo")


def test_default_theme_is_valid() -> None:
    theme = load_theme(ROOT / "themes", "default")
    assert theme.name == "default"
    assert "rm" in theme.locales


def test_missing_theme_json_raises(tmp_path: Path) -> None:
    (tmp_path / "themes" / "demo").mkdir(parents=True)
    with pytest.raises(ThemeValidationError, match=r"theme\.json"):
        load_theme(tmp_path / "themes", "demo")


def test_malformed_json_raises(make_theme: MakeTheme) -> None:
    _expect_error(make_theme, "{ non json", "JSON")


def test_name_must_match_directory(make_theme: MakeTheme, theme_data: dict[str, Any]) -> None:
    theme_file = make_theme(theme_data, name="demo") / "demo" / "theme.json"
    theme_file.write_text(
        theme_file.read_text(encoding="utf-8").replace('"demo"', '"altro"'), encoding="utf-8"
    )
    with pytest.raises(ThemeValidationError, match="name"):
        load_theme(theme_file.parents[1], "demo")


def test_unknown_top_level_key_rejected(make_theme: MakeTheme, theme_data: dict[str, Any]) -> None:
    theme_data["custom_css"] = "body{display:none}"
    _expect_error(make_theme, theme_data, "custom_css")


@pytest.mark.parametrize("bad_type", ["css", "html", "code", "script", "js"])
def test_unknown_setting_type_rejected(
    make_theme: MakeTheme, theme_data: dict[str, Any], bad_type: str
) -> None:
    theme_data["settings"]["extra"] = {"type": bad_type, "label": "X"}
    _expect_error(make_theme, theme_data, "settings/extra")


@pytest.mark.parametrize("bad_key", ["custom_css", "header_html", "tracking_script", "embed_code"])
def test_suspicious_setting_key_rejected(
    make_theme: MakeTheme, theme_data: dict[str, Any], bad_key: str
) -> None:
    theme_data["settings"][bad_key] = {"type": "text", "label": "X"}
    _expect_error(make_theme, theme_data, bad_key)


def test_setting_without_label_rejected(make_theme: MakeTheme, theme_data: dict[str, Any]) -> None:
    theme_data["settings"]["footer_note"].pop("label")
    _expect_error(make_theme, theme_data, "label")


def test_select_default_must_be_in_options(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    theme_data["settings"]["header_style"]["default"] = "neon"
    _expect_error(make_theme, theme_data, "header_style")


def test_select_requires_options(make_theme: MakeTheme, theme_data: dict[str, Any]) -> None:
    theme_data["settings"]["header_style"].pop("options")
    _expect_error(make_theme, theme_data, "header_style")


@pytest.mark.parametrize("bad_color", ["red", "#12345", "#GGGGGG", "url(x)"])
def test_color_must_be_hex(
    make_theme: MakeTheme, theme_data: dict[str, Any], bad_color: str
) -> None:
    theme_data["settings"]["accent_color"]["palette"].append(bad_color)
    _expect_error(make_theme, theme_data, "accent_color")


def test_color_default_must_be_in_palette(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    theme_data["settings"]["accent_color"]["default"] = "#ABCDEF"
    _expect_error(make_theme, theme_data, "accent_color")


def test_block_variants_valid(make_theme: MakeTheme, theme_data: dict[str, Any]) -> None:
    theme_data["block_variants"] = VARIANTS
    themes_dir = make_theme(theme_data, thumbnails=THUMBS)
    theme = load_theme(themes_dir, "demo")
    assert theme.variants_for("text_image") is not None


def test_block_variants_default_must_be_among_options(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    theme_data["block_variants"] = {"text_image": {**VARIANTS["text_image"], "default": "neon"}}
    _expect_error(make_theme, theme_data, "text_image", thumbnails=THUMBS)


def test_block_variants_empty_options_rejected(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    theme_data["block_variants"] = {"text_image": {"default": "x", "options": {}}}
    _expect_error(make_theme, theme_data, "text_image")


@pytest.mark.parametrize("bad_key", ["Dark", "1col", "dark-mode", "x y"])
def test_block_variant_key_pattern(
    make_theme: MakeTheme, theme_data: dict[str, Any], bad_key: str
) -> None:
    option = {"label": "X", "thumbnail": "variants/ti-left.webp"}
    theme_data["block_variants"] = {
        "text_image": {"default": bad_key, "options": {bad_key: option}}
    }
    _expect_error(make_theme, theme_data, "text_image", thumbnails=THUMBS)


@pytest.mark.parametrize(
    "bad_thumb", ["../x.webp", "/abs.webp", "variants/x.js", "variants/../../x.webp", "x.webp"]
)
def test_block_variant_thumbnail_path_rejected(
    make_theme: MakeTheme, theme_data: dict[str, Any], bad_thumb: str
) -> None:
    theme_data["block_variants"] = {
        "text_image": {
            "default": "dark",
            "options": {"dark": {"label": "Sfondo scuro", "thumbnail": bad_thumb}},
        }
    }
    _expect_error(make_theme, theme_data, "thumbnail")


def test_block_variant_missing_thumbnail_file_rejected(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    """D-18: una miniatura dichiarata ma assente blocca l'avvio."""
    theme_data["block_variants"] = VARIANTS
    _expect_error(make_theme, theme_data, "ti-left.webp", thumbnails=THUMBS[1:])


def test_block_variants_unknown_block_type_rejected(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    theme_data["block_variants"] = {"carousel": VARIANTS["text_image"]}
    _expect_error(make_theme, theme_data, "carousel", thumbnails=THUMBS)


def test_zone_unknown_block_rejected(make_theme: MakeTheme, theme_data: dict[str, Any]) -> None:
    theme_data["layouts"]["page"]["zones"]["main"]["blocks"].append("raw_html")
    _expect_error(make_theme, theme_data, "raw_html")


def test_zone_max_positive(make_theme: MakeTheme, theme_data: dict[str, Any]) -> None:
    theme_data["layouts"]["page"]["zones"]["sidebar"]["max"] = 0
    _expect_error(make_theme, theme_data, "sidebar")


def test_widget_area_unknown_widget_rejected(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    theme_data["widget_areas"]["footer"]["widgets"].append("iframe")
    _expect_error(make_theme, theme_data, "iframe")


def test_collection_unknown_field_type_rejected(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    theme_data["collections"]["news"]["fields"]["snippet"] = {"type": "html"}
    _expect_error(make_theme, theme_data, "snippet")


def test_unknown_locale_rejected(make_theme: MakeTheme, theme_data: dict[str, Any]) -> None:
    theme_data["locales"].append("fr")
    _expect_error(make_theme, theme_data, "locales")


@pytest.mark.parametrize("bad_key", ["custom_style", "head_extra", "raw_markup", "js_snippet"])
def test_more_suspicious_setting_keys_rejected(
    make_theme: MakeTheme, theme_data: dict[str, Any], bad_key: str
) -> None:
    theme_data["settings"][bad_key] = {"type": "textarea", "label": "X", "max": 100}
    _expect_error(make_theme, theme_data, bad_key)


@pytest.mark.parametrize("good_key", ["site_description", "postcode", "zip_code", "headline"])
def test_legit_setting_keys_accepted(
    make_theme: MakeTheme, theme_data: dict[str, Any], good_key: str
) -> None:
    """Niente falsi positivi: la sicurezza vera è l'allowlist dei tipi."""
    theme_data["settings"][good_key] = {"type": "text", "label": "X", "max": 100}
    assert good_key in load_theme(make_theme(theme_data), "demo").settings


@pytest.mark.parametrize("kind", ["text", "textarea"])
def test_text_settings_require_max(
    make_theme: MakeTheme, theme_data: dict[str, Any], kind: str
) -> None:
    theme_data["settings"]["slogan"] = {"type": kind, "label": "Slogan"}
    _expect_error(make_theme, theme_data, "slogan")


@pytest.mark.parametrize("bad_url", ["javascript:alert(1)", "data:text/html,x", "//evil.ch"])
def test_url_default_must_be_http_or_relative(
    make_theme: MakeTheme, theme_data: dict[str, Any], bad_url: str
) -> None:
    theme_data["settings"]["link"] = {"type": "url", "label": "Link", "default": bad_url}
    _expect_error(make_theme, theme_data, "link")


def test_url_default_https_accepted(make_theme: MakeTheme, theme_data: dict[str, Any]) -> None:
    theme_data["settings"]["link"] = {"type": "url", "label": "Link", "default": "https://x.ch"}
    assert load_theme(make_theme(theme_data), "demo").setting("link").default == "https://x.ch"


def test_media_default_must_be_null(make_theme: MakeTheme, theme_data: dict[str, Any]) -> None:
    theme_data["settings"]["logo"] = {"type": "media", "label": "Logo", "default": "/x.png"}
    _expect_error(make_theme, theme_data, "logo")


def test_color_default_case_insensitive(make_theme: MakeTheme, theme_data: dict[str, Any]) -> None:
    theme_data["settings"]["accent_color"]["default"] = "#0b5fff"
    assert load_theme(make_theme(theme_data), "demo").setting("accent_color").default == "#0B5FFF"


def test_duplicate_json_keys_rejected(make_theme: MakeTheme, theme_data: dict[str, Any]) -> None:
    raw = json.dumps({**theme_data, "name": "demo"})
    raw = raw[:-1] + ', "settings": {}}'
    _expect_error(make_theme, raw, "duplicat")


def test_nan_rejected(make_theme: MakeTheme, theme_data: dict[str, Any]) -> None:
    raw = json.dumps({**theme_data, "name": "demo"})
    raw = raw.replace('"width": 320', '"width": NaN')
    _expect_error(make_theme, raw, "NaN")


def test_empty_thumbnail_file_rejected(make_theme: MakeTheme, theme_data: dict[str, Any]) -> None:
    theme_data["block_variants"] = VARIANTS
    themes_dir = make_theme(theme_data, thumbnails=THUMBS)
    (themes_dir / "demo" / "assets" / THUMBS[0]).write_bytes(b"")
    with pytest.raises(ThemeValidationError, match="vuot"):
        load_theme(themes_dir, "demo")


def test_thumbnail_with_trailing_newline_rejected(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    option = {"label": "Scuro", "thumbnail": "variants/ti-dark.webp\n"}
    theme_data["block_variants"] = {"text_image": {"default": "dark", "options": {"dark": option}}}
    _expect_error(make_theme, theme_data, "thumbnail", thumbnails=THUMBS)


def test_key_with_trailing_newline_rejected(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    theme_data["settings"]["slogan\n"] = {"type": "boolean", "label": "X"}
    _expect_error(make_theme, theme_data, "settings")


@pytest.mark.parametrize("bad_name", ["../etc", "Default", "a/b", "", ".hidden"])
def test_active_theme_name_traversal_rejected(tmp_path: Path, bad_name: str) -> None:
    with pytest.raises(ThemeValidationError, match="nome"):
        load_theme(tmp_path, bad_name)


# --- Miniature verificate sui byte (D-63) ---------------------------------------------


@pytest.mark.parametrize("name", ["variants/a.png", "variants/a.jpg", "variants/a.webp"])
def test_real_image_thumbnails_accepted(
    make_theme: MakeTheme, theme_data: dict[str, Any], name: str
) -> None:
    option = {"label": "Scuro", "thumbnail": name}
    theme_data["block_variants"] = {"text_image": {"default": "dark", "options": {"dark": option}}}
    load_theme(make_theme(theme_data, thumbnails=[name]), "demo")


@pytest.mark.parametrize(
    ("content", "match"),
    [
        (b"non sono un'immagine", "PNG, JPG o WebP"),
        (b"GIF89a" + bytes(10), "PNG, JPG o WebP"),
        (FAKE_IMAGES[".png"], "PNG, JPG o WebP"),  # PNG vero con estensione .webp
        (b"RIFF" + bytes(4) + b"WAVEfmt ", "PNG, JPG o WebP"),
    ],
)
def test_fake_thumbnails_rejected(
    make_theme: MakeTheme, theme_data: dict[str, Any], content: bytes, match: str
) -> None:
    theme_data["block_variants"] = VARIANTS
    themes_dir = make_theme(theme_data, thumbnails=THUMBS)
    (themes_dir / "demo" / "assets" / THUMBS[0]).write_bytes(content)
    with pytest.raises(ThemeValidationError, match=match):
        load_theme(themes_dir, "demo")


def test_collection_per_page_bounded(make_theme: MakeTheme, theme_data: dict[str, Any]) -> None:
    theme_data["collections"]["news"]["per_page"] = 500
    _expect_error(make_theme, theme_data, "per_page")


def test_listing_layout_must_name_a_declared_collection(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    theme_data["layouts"]["news_list"]["collection"] = "eventi"
    _expect_error(make_theme, theme_data, "eventi")


def test_one_listing_layout_per_collection(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    """D-149: una sola pagina elenco per raccolta, quindi un solo layout che la elenca."""
    theme_data["layouts"]["altro_elenco"] = {
        **theme_data["layouts"]["news_list"],
        "label": "Altro elenco",
    }
    _expect_error(make_theme, theme_data, "news")
