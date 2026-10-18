"""Documento della bozza: forma, blocchi e regole del tema (D-03, D-46)."""

from __future__ import annotations

from typing import Any

import pytest

from app.services.blocks import Mode
from app.services.content import MAX_BLOCKS, validate_document
from app.services.errors import ServiceError
from app.services.theme import Theme, load_theme
from tests.conftest import ROOT, MakeTheme
from tests.pages_helpers import doc, heading_block, text_block, uid
from tests.unit.test_theme_schema import THUMBS, VARIANTS


@pytest.fixture
def theme(make_theme: MakeTheme, theme_data: dict[str, Any]) -> Theme:
    theme_data["block_variants"] = VARIANTS
    return load_theme(make_theme(theme_data, thumbnails=THUMBS), "demo")


def _errors(theme: Theme, document: Any, mode: Mode = Mode.DRAFT) -> set[tuple[str, str]]:
    with pytest.raises(ServiceError) as exc:
        validate_document(theme, document, mode)
    assert exc.value.status == 422
    assert exc.value.code == "invalid_content"
    return {(d["path"], d["code"]) for d in exc.value.details}


def _text_image(n: int, **extra: Any) -> dict[str, Any]:
    return {"uid": uid(n), "type": "text_image", "data": {"media_id": 1}, **extra}


def test_valid_document_is_cleaned(theme: Theme) -> None:
    document = doc(
        title="  Chi siamo  ",
        zones={"main": [text_block(1, '<p onclick="x">Ciao</p>')], "sidebar": []},
        seo={"title": " SEO ", "noindex": False},
    )
    result = validate_document(theme, document, Mode.PUBLISH)
    assert result["title"] == "Chi siamo"
    assert result["seo"] == {"title": "SEO", "noindex": False}
    assert result["zones"]["main"][0]["data"] == {"body": "<p>Ciao</p>"}
    assert document["zones"]["main"][0]["data"]["body"] == '<p onclick="x">Ciao</p>'


def test_missing_zones_are_added_empty(theme: Theme) -> None:
    result = validate_document(theme, doc(zones={"main": [text_block(1)]}), Mode.DRAFT)
    assert result["zones"]["sidebar"] == []


def test_unknown_layout(theme: Theme) -> None:
    assert ("layout", "unknown_layout") in _errors(theme, doc(layout="landing"))


def test_unknown_zone(theme: Theme) -> None:
    assert ("zones/aside", "unknown_zone") in _errors(
        theme, doc(zones={"main": [], "aside": [text_block(1)]})
    )


def test_layout_change_leaves_blocks_in_missing_zone(theme: Theme) -> None:
    document = doc(layout="full", zones={"main": [], "sidebar": [text_block(1)]})
    assert ("zones/sidebar", "unknown_zone") in _errors(theme, document)


def test_block_type_not_allowed_in_zone(theme: Theme) -> None:
    hero = {"uid": uid(1), "type": "hero", "data": {}}
    assert ("zones/main/0/type", "block_not_allowed") in _errors(
        theme, doc(zones={"main": [hero], "sidebar": []})
    )


def test_zone_max_for_home_hero(theme: Theme) -> None:
    heroes = [{"uid": uid(n), "type": "hero", "data": {}} for n in (1, 2)]
    document = doc(layout="home", zones={"hero": heroes, "main": []})
    assert ("zones/hero", "zone_full") in _errors(theme, document)


def test_zone_max_for_sidebar(theme: Theme) -> None:
    document = doc(zones={"main": [], "sidebar": [text_block(n) for n in range(1, 6)]})
    assert ("zones/sidebar", "zone_full") in _errors(theme, document)


def test_missing_variant_gets_theme_default(theme: Theme) -> None:
    document = doc(zones={"main": [_text_image(1)], "sidebar": []})
    result = validate_document(theme, document, Mode.DRAFT)
    assert result["zones"]["main"][0]["variant"] == "image_left"


def test_declared_variant_is_kept(theme: Theme) -> None:
    document = doc(zones={"main": [_text_image(1, variant="dark")], "sidebar": []})
    result = validate_document(theme, document, Mode.DRAFT)
    assert result["zones"]["main"][0]["variant"] == "dark"


def test_undeclared_variant(theme: Theme) -> None:
    document = doc(zones={"main": [_text_image(1, variant="neon")], "sidebar": []})
    assert ("zones/main/0/variant", "unknown_variant") in _errors(theme, document)


def test_variant_on_block_without_variants(theme: Theme) -> None:
    document = doc(zones={"main": [text_block(1, variant="dark")], "sidebar": []})
    assert ("zones/main/0/variant", "variant_not_supported") in _errors(theme, document)


def test_block_without_variants_stores_none() -> None:
    default = load_theme(ROOT / "themes", "default")
    image = {"uid": uid(1), "type": "image", "data": {"media_id": 1}}
    result = validate_document(default, doc(zones={"main": [image]}), Mode.DRAFT)
    assert result["zones"]["main"][0]["variant"] is None


def test_duplicate_uid_across_zones(theme: Theme) -> None:
    document = doc(zones={"main": [text_block(1)], "sidebar": [text_block(1)]})
    assert ("zones/sidebar/0/uid", "duplicate_uid") in _errors(theme, document)


@pytest.mark.parametrize("bad_uid", ["A" * 32, "a" * 31, "z" * 32, ""])
def test_invalid_uid(theme: Theme, bad_uid: str) -> None:
    block = {**text_block(1), "uid": bad_uid}
    assert ("zones/main/0/uid", "pattern") in _errors(theme, doc(zones={"main": [block]}))


def test_unknown_block_type(theme: Theme) -> None:
    block = {"uid": uid(1), "type": "carousel", "data": {}}
    assert ("zones/main/0/type", "enum") in _errors(theme, doc(zones={"main": [block]}))


def test_block_data_errors_have_full_path(theme: Theme) -> None:
    document = doc(zones={"main": [heading_block(1, "x" * 201)], "sidebar": []})
    assert ("zones/main/0/data/text", "maxLength") in _errors(theme, document)


def test_required_fields_only_block_publishing(theme: Theme) -> None:
    document = doc(title="", zones={"main": [text_block(1, "")], "sidebar": []})
    validate_document(theme, document, Mode.DRAFT)
    assert _errors(theme, document, Mode.PUBLISH) == {
        ("title", "required"),
        ("zones/main/0/data/body", "required"),
    }


def test_extra_keys_are_rejected(theme: Theme) -> None:
    document = {**doc(), "template": "<script>"}
    assert ("template", "additionalProperties") in _errors(theme, document)


def test_seo_limits(theme: Theme) -> None:
    document = doc(seo={"title": "x" * 71, "og_image_media_id": 0})
    assert {("seo/title", "maxLength"), ("seo/og_image_media_id", "minimum")} <= _errors(
        theme, document
    )


def test_too_many_blocks(theme: Theme) -> None:
    blocks = [heading_block(n) for n in range(1, MAX_BLOCKS + 2)]
    assert ("zones", "too_many_blocks") in _errors(theme, doc(zones={"main": blocks}))


def test_document_too_large_is_413(theme: Theme) -> None:
    blocks = [text_block(n, "<p>" + "x" * 9000 + "</p>") for n in range(1, 60)]
    with pytest.raises(ServiceError) as exc:
        validate_document(theme, doc(zones={"main": blocks}), Mode.DRAFT)
    assert exc.value.status == 413


def test_document_must_be_an_object(theme: Theme) -> None:
    assert ("", "type") in _errors(theme, ["non", "un", "oggetto"])
