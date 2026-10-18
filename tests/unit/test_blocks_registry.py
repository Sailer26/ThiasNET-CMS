"""Registry dei blocchi: schemi JSON dei 13 tipi base, validazione bozza/pubblica e pulizia."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.core_types import BLOCK_TYPES
from app.services.blocks import (
    BLOCKS_DIR,
    BlockRegistry,
    BlockRegistryError,
    FieldError,
    Mode,
    _without_publish_rules,
    get_registry,
    load_registry,
)

VALID: dict[str, dict[str, Any]] = {
    "hero": {
        "title": "Benvenuti",
        "subtitle": "Il nostro comune",
        "media_id": 1,
        "cta_label": "Scopri",
        "cta_url": "/chi-siamo",
    },
    "heading": {"text": "Chi siamo", "level": 3, "anchor": "chi-siamo"},
    "text": {"body": "<p>Ciao <strong>mondo</strong></p>"},
    "image": {"media_id": 3, "caption": "Foto", "link": "https://example.ch/pagina"},
    "gallery": {"items": [{"media_id": 1, "caption": "Uno"}, {"media_id": 2}]},
    "text_image": {
        "title": "Storia",
        "body": "<p>Testo</p>",
        "media_id": 4,
        "cta_label": "Scrivici",
        "cta_url": "mailto:info@example.ch",
    },
    "cta": {
        "title": "Contattaci",
        "text": "Siamo a disposizione",
        "button_label": "Chiama",
        "url": "tel:+41911234567",
    },
    "quote": {"text": "Una citazione", "author": "Anna", "role": "Sindaca"},
    "video": {"provider": "youtube", "video_id": "dQw4w9WgXcQ", "title": "Presentazione"},
    "divider": {},
    "map": {"lat": 46.0037, "lng": 8.9511, "zoom": 14, "label": "Sede", "address": "Via Roma 1"},
    "files": {"title": "Documenti", "items": [{"media_id": 7, "label": "Regolamento"}]},
    "contacts": {
        "title": "Contatti",
        "intro": "Scrivici",
        "address": "Via Roma 1, 6900 Lugano",
        "phone": "+41 91 123 45 67",
        "email": "info@example.ch",
        "show_form": True,
    },
}

INVALID: list[tuple[str, dict[str, Any], str]] = [
    ("text", {"body": "<p>x</p>", "extra": 1}, "additionalProperties"),
    ("divider", {"x": 1}, "additionalProperties"),
    ("heading", {"text": "x" * 201}, "maxLength"),
    ("heading", {"text": "x", "level": 1}, "enum"),
    ("heading", {"text": "x", "anchor": "Non Valida"}, "pattern"),
    ("image", {"media_id": "1"}, "type"),
    ("image", {"media_id": 0}, "minimum"),
    ("image", {"media_id": True}, "type"),
    ("image", {"media_id": 1, "link": "javascript:alert(1)"}, "format"),
    ("image", {"media_id": 1, "link": "JaVaScRiPt:alert(1)"}, "format"),
    ("image", {"media_id": 1, "link": "//evil.com"}, "format"),
    ("image", {"media_id": 1, "link": "/\\evil.com"}, "format"),
    ("image", {"media_id": 1, "link": "data:text/html;base64,PHNjcmlwdD4="}, "format"),
    ("image", {"media_id": 1, "link": "vbscript:msgbox(1)"}, "format"),
    ("image", {"media_id": 1, "link": "https://"}, "format"),
    ("image", {"media_id": 1, "link": "pagina-relativa"}, "format"),
    ("cta", {"title": "a", "button_label": "b", "url": "https://exa mple.ch"}, "format"),
    ("video", {"provider": "youtube", "video_id": "abc", "title": "x"}, "pattern"),
    ("video", {"provider": "vimeo", "video_id": "dQw4w9WgXcQ", "title": "x"}, "pattern"),
    ("video", {"provider": "dailymotion", "video_id": "123", "title": "x"}, "enum"),
    ("map", {"lat": 91, "lng": 0}, "maximum"),
    ("map", {"lat": 0, "lng": -181}, "minimum"),
    ("map", {"lat": 0, "lng": 0, "zoom": 20}, "maximum"),
    ("gallery", {"items": [{"media_id": 1}] * 49}, "maxItems"),
    ("gallery", {"items": [{"media_id": 1, "html": "<b>"}]}, "additionalProperties"),
    ("hero", {"title": "x", "media_id": 1, "cta_label": "Vai"}, "dependentRequired"),
    ("contacts", {"phone": "<script>"}, "pattern"),
    ("contacts", {"email": "non-una-email"}, "pattern"),
    ("files", {"items": [{"media_id": 1}] * 51}, "maxItems"),
]


@pytest.fixture
def registry() -> BlockRegistry:
    return get_registry()


def _codes(errors: list[FieldError]) -> set[str]:
    return {e.code for e in errors}


# --- Caricamento -------------------------------------------------------------


def test_registry_covers_exactly_the_core_block_types(registry: BlockRegistry) -> None:
    assert registry.types == BLOCK_TYPES


def _copy_schemas(target: Path, skip: str | None = None) -> Path:
    target.mkdir()
    for path in BLOCKS_DIR.glob("*.schema.json"):
        if path.name != f"{skip}.schema.json":
            (target / path.name).write_bytes(path.read_bytes())
    return target


def test_missing_schema_fails_loading(tmp_path: Path) -> None:
    with pytest.raises(BlockRegistryError, match="video"):
        load_registry(_copy_schemas(tmp_path / "blocks", skip="video"))


def test_unknown_schema_fails_loading(tmp_path: Path) -> None:
    directory = _copy_schemas(tmp_path / "blocks")
    (directory / "carousel.schema.json").write_text(json.dumps({"type": "object"}))
    with pytest.raises(BlockRegistryError, match="carousel"):
        load_registry(directory)


def test_broken_schema_fails_loading(tmp_path: Path) -> None:
    directory = _copy_schemas(tmp_path / "blocks")
    (directory / "divider.schema.json").write_text(json.dumps({"type": "oggetto"}))
    with pytest.raises(BlockRegistryError, match="divider"):
        load_registry(directory)


def test_registry_schemas_are_read_only(registry: BlockRegistry) -> None:
    with pytest.raises(TypeError):
        registry.schema("divider")["type"] = "string"  # type: ignore[index]


# --- Meta-test sugli schemi ----------------------------------------------------

FORBIDDEN_FIELD_WORDS = ("html", "raw", "embed", "script", "style", "iframe", "css")


def _walk(schema: Any, where: str) -> Iterator[tuple[str, Any]]:
    yield where, schema
    for name, sub in schema.get("properties", {}).items():
        yield from _walk(sub, f"{where}.{name}")
    if "items" in schema:
        yield from _walk(schema["items"], f"{where}[]")


@pytest.mark.parametrize("block_type", sorted(BLOCK_TYPES))
def test_schema_is_closed_and_bounded(registry: BlockRegistry, block_type: str) -> None:
    for where, node in _walk(registry.schema(block_type), block_type):
        kind = node.get("type")
        if kind == "object":
            assert node.get("additionalProperties") is False, f"{where}: oggetto aperto"
            for name in node.get("properties", {}):
                assert not any(w in name.lower() for w in FORBIDDEN_FIELD_WORDS), where
        if kind == "string":
            assert any(k in node for k in ("maxLength", "enum")), f"{where}: illimitato"
            if node.get("x-richtext"):
                assert node["maxLength"] <= 20000, where
        if kind == "array":
            assert "maxItems" in node, f"{where}: array senza maxItems"
        if node.get("x-media"):
            assert kind == "integer" and node.get("minimum") == 1, where


# --- Validazione -------------------------------------------------------------


@pytest.mark.parametrize("block_type", sorted(VALID))
def test_valid_examples_pass_in_publish_mode(registry: BlockRegistry, block_type: str) -> None:
    data = registry.clean(block_type, VALID[block_type])
    assert registry.errors(block_type, data, Mode.PUBLISH) == []


@pytest.mark.parametrize(("block_type", "data", "code"), INVALID)
def test_invalid_examples_fail(
    registry: BlockRegistry, block_type: str, data: dict[str, Any], code: str
) -> None:
    cleaned = registry.clean(block_type, data)
    errors = registry.errors(block_type, cleaned, Mode.DRAFT)
    errors += registry.errors(block_type, cleaned, Mode.PUBLISH)
    assert code in _codes(errors)
    assert all(e.message and e.path.startswith("data") for e in errors)


def test_required_fields_are_ignored_in_draft_mode(registry: BlockRegistry) -> None:
    assert registry.errors("hero", {}, Mode.DRAFT) == []
    errors = registry.errors("hero", {}, Mode.PUBLISH)
    assert {e.path for e in errors} == {"data/title", "data/media_id"}
    assert {e.message for e in errors} == {"Campo obbligatorio"}


def test_min_items_only_matters_when_publishing(registry: BlockRegistry) -> None:
    assert registry.errors("gallery", {"items": []}, Mode.DRAFT) == []
    assert "minItems" in _codes(registry.errors("gallery", {"items": []}, Mode.PUBLISH))


def test_errors_are_in_italian_with_path(registry: BlockRegistry) -> None:
    errors = registry.errors("heading", {"text": "x" * 201}, Mode.DRAFT)
    assert errors[0].path == "data/text"
    assert errors[0].message == "Al massimo 200 caratteri"


def test_vimeo_id_is_numeric(registry: BlockRegistry) -> None:
    data = {"provider": "vimeo", "video_id": "76979871", "title": "x"}
    assert registry.errors("video", data, Mode.PUBLISH) == []


def test_unknown_block_type_is_an_error(registry: BlockRegistry) -> None:
    assert _codes(registry.errors("carousel", {}, Mode.DRAFT)) == {"unknown_type"}


# --- Pulizia delle stringhe ----------------------------------------------------


def test_plain_strings_are_never_html(registry: BlockRegistry) -> None:
    data = registry.clean("quote", {"text": "<script>alert(1)</script>"})
    assert data["text"] == "<script>alert(1)</script>"  # letterale: lo escapa il tema


def test_plain_strings_are_normalized(registry: BlockRegistry) -> None:
    raw = {"text": "  Caffè\x00\x07 al\r\nbar\t ", "author": "  "}
    assert registry.clean("quote", raw) == {"text": "Caffè al\nbar"}


def test_richtext_is_sanitized_on_clean(registry: BlockRegistry) -> None:
    data = registry.clean("text", {"body": '<p onclick="x()">Ciao<script>x</script></p>'})
    assert data["body"] == "<p>Ciao</p>"


def test_empty_richtext_counts_as_missing(registry: BlockRegistry) -> None:
    data = registry.clean("text", {"body": "<script>alert(1)</script>"})
    assert "body" not in data
    assert registry.errors("text", data, Mode.PUBLISH)[0].code == "required"


def test_nested_strings_are_cleaned(registry: BlockRegistry) -> None:
    data = registry.clean("gallery", {"items": [{"media_id": 1, "caption": "  a\x00 "}]})
    assert data == {"items": [{"media_id": 1, "caption": "a"}]}


def test_clean_leaves_wrong_types_to_validation(registry: BlockRegistry) -> None:
    data = registry.clean("quote", {"text": 42, "author": ["x"]})
    assert data == {"text": 42, "author": ["x"]}
    assert "type" in _codes(registry.errors("quote", data, Mode.DRAFT))


def test_clean_does_not_mutate_input(registry: BlockRegistry) -> None:
    original = {"text": "  x  "}
    registry.clean("quote", original)
    assert original == {"text": "  x  "}


def test_media_ids(registry: BlockRegistry) -> None:
    assert registry.media_ids("hero", VALID["hero"]) == (1,)
    assert registry.media_ids("gallery", VALID["gallery"]) == (1, 2)
    assert registry.media_ids("divider", {}) == ()
    assert registry.media_ids("text_image", {"title": "x"}) == ()


def test_draft_mode_keeps_fields_named_like_keywords() -> None:
    schema = {
        "type": "object",
        "required": ["required"],
        "properties": {"required": {"type": "string", "maxLength": 5}},
    }
    assert _without_publish_rules(schema) == {
        "type": "object",
        "properties": {"required": {"type": "string", "maxLength": 5}},
    }


def test_tabs_become_spaces_and_emoji_joiners_survive(registry: BlockRegistry) -> None:
    emoji = chr(0x1F469) + chr(0x200D) + chr(0x1F4BB)  # donna al computer: ZWJ da tenere
    raw = f"uno{chr(9)}due {emoji} {chr(0x202E)}abc"  # tab e RLO (testo rovesciato)
    assert registry.clean("quote", {"text": raw})["text"] == f"uno due {emoji} abc"


@pytest.mark.parametrize("anchor", ["main", "site-nav", "cms-consent"])
def test_heading_anchor_cannot_reuse_reserved_ids(registry: BlockRegistry, anchor: str) -> None:
    errors = registry.errors("heading", {"text": "x", "anchor": anchor}, Mode.DRAFT)
    assert errors and errors[0].path == "data/anchor"
