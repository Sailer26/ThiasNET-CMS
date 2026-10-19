"""Renderer del sito (D-52, D-53, D-56, D-57, D-60) con il tema `default`."""

from __future__ import annotations

from typing import Any

import pytest

from app.services.render import Renderer
from app.services.render_context import Link, RenderMode
from app.services.theme import Theme, load_theme
from tests.conftest import ROOT, MakeTheme
from tests.pages_helpers import doc, uid
from tests.render_fixtures import inspect, render_doc
from tests.unit.test_blocks_registry import VALID


@pytest.fixture(scope="module")
def theme() -> Theme:
    return load_theme(ROOT / "themes", "default")


def _block(n: int, block_type: str, data: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"uid": uid(n), "type": block_type, "data": data, **extra}


def _page(*blocks: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return doc(zones={"main": list(blocks), "sidebar": []}, **extra)


# --- Blocchi ---------------------------------------------------------------------

MAIN_TYPES = sorted(set(VALID) - {"hero"})


@pytest.mark.parametrize("block_type", MAIN_TYPES)
def test_every_block_has_data_block_id_on_its_root(theme: Theme, block_type: str) -> None:
    html = render_doc(theme, _page(_block(7, block_type, VALID[block_type])))
    roots = [a for _, a in inspect(html).tags if a.get("data-block-id") == uid(7)]
    assert len(roots) == 1, block_type


@pytest.mark.parametrize("block_type", MAIN_TYPES)
def test_every_block_survives_minimal_data(theme: Theme, block_type: str) -> None:
    html = render_doc(theme, _page(_block(7, block_type, {})))
    assert f'data-block-id="{uid(7)}"' in html


def test_hero_on_home_with_variant_class(theme: Theme) -> None:
    hero = _block(1, "hero", VALID["hero"], variant="split")
    document = doc(layout="home", zones={"hero": [hero], "main": []})
    html = render_doc(theme, document, path="/", is_home=True)
    assert "hero--split" in html
    assert len(inspect(html).find("h1")) == 1


def test_variant_classes_and_defaults(theme: Theme) -> None:
    html = render_doc(theme, _page(_block(1, "cta", VALID["cta"], variant="dark")))
    assert "cta--dark" in html
    html = render_doc(theme, _page(_block(1, "quote", VALID["quote"])))
    assert "quote--simple" in html  # nessuna variante salvata: default del tema


# --- Contenuto non più coerente col tema (D-53) ------------------------------------------


def test_stale_content_never_breaks_the_page(theme: Theme) -> None:
    document = {
        "title": "Vecchia",
        "layout": "landing",  # layout sparito: si usa "page"
        "seo": {},
        "zones": {
            "main": [
                _block(1, "text", {"body": "<p>Resta</p>"}),
                _block(2, "hero", VALID["hero"]),  # non ammesso in main: omesso
                _block(3, "cta", VALID["cta"], variant="neon"),  # variante sparita: default
            ],
            "aside": [_block(4, "text", {"body": "<p>Zona sparita</p>"})],
        },
    }
    html = render_doc(theme, document)
    assert "Resta" in html
    assert uid(2) not in html and "Zona sparita" not in html
    assert "cta--light" in html and "neon" not in html


# --- Sicurezza del contenuto -------------------------------------------------------------


def test_plain_text_is_escaped(theme: Theme) -> None:
    html = render_doc(theme, _page(_block(1, "quote", {"text": "<b>{{ 7*7 }}</b>"})))
    assert "&lt;b&gt;{{ 7*7 }}&lt;/b&gt;" in html
    assert "49" not in html


def test_richtext_is_sanitized_again_on_output(theme: Theme) -> None:
    body = '<p onclick="x()">Ciao<script>alert(1)</script></p>'  # salvato senza passare dai servizi
    html = render_doc(theme, _page(_block(1, "text", {"body": body})))
    assert "<p>Ciao</p>" in html
    assert "alert(1)" not in html and "onclick" not in html


def test_unsafe_link_in_stored_data_is_dropped(theme: Theme) -> None:
    data = {"title": "x", "button_label": "Vai", "url": "javascript:alert(1)"}
    html = render_doc(theme, _page(_block(1, "cta", data)))
    assert "javascript:" not in html


def test_no_inline_script_style_or_event_handlers(theme: Theme) -> None:
    blocks = [_block(n, t, VALID[t]) for n, t in enumerate(MAIN_TYPES, start=1)]
    page = inspect(render_doc(theme, _page(*blocks)))
    assert page.inline_scripts == 0
    assert not page.find("style")
    for _, attrs in page.tags:
        assert "style" not in attrs
        assert not any(name.startswith("on") for name in attrs)


# --- Helper del contratto ---------------------------------------------------------------


def test_head_has_title_description_canonical(theme: Theme) -> None:
    html = render_doc(theme, _page(seo={"description": "Descrizione"}))
    page = inspect(html)
    assert "<title>Chi siamo | Comune di Prova</title>" in html
    assert {"name": "description", "content": "Descrizione"} in page.find("meta")
    assert {"rel": "canonical", "href": "https://www.example.ch/chi-siamo"} in page.find("link")
    assert not [m for m in page.find("meta") if m.get("name") == "robots"]


def test_noindex_and_custom_seo_title(theme: Theme) -> None:
    html = render_doc(theme, _page(seo={"title": "Titolo SEO", "noindex": True}))
    assert "<title>Titolo SEO</title>" in html
    assert {"name": "robots", "content": "noindex"} in inspect(html).find("meta")


def test_assets_are_versioned(theme: Theme) -> None:
    links = inspect(render_doc(theme, _page())).find("link")
    css = [a["href"] for a in links if a.get("rel") == "stylesheet"]
    assert any(h and h.startswith("/assets/css/site.css?v=") for h in css)
    assert any(h and h.startswith("/_vars.css?v=") for h in css)


def test_images_are_empty_until_the_media_library(theme: Theme) -> None:
    page = _page(_block(1, "image", VALID["image"]))
    assert "cms-media-placeholder" not in render_doc(theme, page)
    assert "cms-media-placeholder" in render_doc(theme, page, mode=RenderMode.PREVIEW)


def test_unknown_image_size_is_an_error_in_strict_mode(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    themes_dir = make_theme(theme_data)
    bad = themes_dir / "demo"
    (bad / "layouts").mkdir()
    (bad / "layouts" / "page.html").write_text("{{ img(1, size='enorme') }}", encoding="utf-8")
    demo = load_theme(themes_dir, "demo")
    with pytest.raises(ValueError, match="enorme"):
        render_doc(demo, _page())
    assert render_doc(demo, _page(), renderer=Renderer(demo, strict=False)) == ""


def test_consent_banner_and_scripts(theme: Theme) -> None:
    public = inspect(render_doc(theme, _page()))
    dialog = [a for _, a in public.tags if a.get("role") == "dialog"]
    assert dialog and dialog[0].get("aria-labelledby") == "cms-consent-title"
    scripts = [a.get("src") or "" for a in public.find("script")]
    assert any(s.startswith("/static/cms/consent.js") for s in scripts)
    assert not any("preview.js" in s for s in scripts)
    preview = [
        a.get("src") or ""
        for a in inspect(render_doc(theme, _page(), mode=RenderMode.PREVIEW)).find("script")
    ]
    assert any("preview.js" in s for s in preview)


def test_embeds_are_click_to_load_placeholders(theme: Theme) -> None:
    youtube = _block(1, "video", VALID["video"])
    vimeo = _block(2, "video", {"provider": "vimeo", "video_id": "76979871", "title": "V"})
    osm = _block(3, "map", VALID["map"])
    html = render_doc(theme, _page(youtube, vimeo, osm))
    assert "<iframe" not in html
    assert "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ" in html
    assert "https://player.vimeo.com/video/76979871?dnt=1" in html
    assert "https://www.openstreetmap.org/export/embed.html" in html
    assert 'href="https://www.youtube.com/watch?v=dQw4w9WgXcQ"' in html


def test_private_vimeo_videos_keep_their_hash(theme: Theme) -> None:
    """D-129: i video Vimeo privati hanno anche un codice (hash) nell'indirizzo."""
    data = {"provider": "vimeo", "video_id": "76979871", "video_hash": "a1b2c3d4e5", "title": "V"}
    html = render_doc(theme, _page(_block(1, "video", data)))
    assert "https://player.vimeo.com/video/76979871?h=a1b2c3d4e5&amp;dnt=1" in html
    assert 'href="https://vimeo.com/76979871/a1b2c3d4e5"' in html


def test_menu_marks_the_current_page(theme: Theme) -> None:
    menu = (Link("Home", "/"), Link("Chi siamo", "/chi-siamo", current=True))
    nav_links = inspect(render_doc(theme, _page(), menu=menu)).find("a")
    current = [a for a in nav_links if a.get("aria-current") == "page"]
    assert current == [{"href": "/chi-siamo", "aria-current": "page"}]


def test_texts_follow_the_page_language(theme: Theme) -> None:
    from app.services.public_texts import LOCALES, TEXTS

    assert all(set(LOCALES) <= set(translations) for translations in TEXTS.values())


# --- Regressioni dalla review ECC della Fase 3 -------------------------------------------


@pytest.mark.parametrize(
    "document",
    [
        ["non", "un", "documento"],
        {"layout": "page", "zones": {"main": 5}},
        {"layout": "page", "zones": {"main": "testo"}},
        {"layout": "page", "zones": {"main": [{"uid": "x", "type": ["text"], "data": {}}]}},
        {"layout": "page", "zones": {"main": [{"uid": 5, "type": "text", "data": "x"}]}},
    ],
)
def test_odd_documents_never_raise(theme: Theme, document: Any) -> None:
    assert "<html" in render_doc(theme, document)


def test_a_broken_block_disappears_but_the_page_stays(
    make_theme: MakeTheme, theme_data: dict[str, Any]
) -> None:
    themes_dir = make_theme(theme_data, templates=True)
    (themes_dir / "demo" / "blocks" / "quote.html").write_text(
        "{% include 'partials/manca.html' %}", encoding="utf-8"
    )
    demo = load_theme(themes_dir, "demo")
    page = _page(_block(1, "quote", {"text": "x"}), _block(2, "text", {"body": "<p>Resto</p>"}))
    html = render_doc(demo, page, renderer=Renderer(demo, strict=False))
    assert "Resto" in html and uid(1) not in html
    with pytest.raises(Exception, match="manca"):
        render_doc(demo, page)  # in sviluppo e nei test l'errore si vede subito


def test_preview_never_loads_statistics(theme: Theme) -> None:
    from app.services.render_context import Analytics, PageContext, normalize_document
    from tests.render_fixtures import SITE

    view = normalize_document(theme, _page(), page_id=1, locale="it", path="/x", is_home=False)
    analytics = Analytics(url="https://stat.example.ch", site_id="3")
    for mode, expected in ((RenderMode.PUBLIC, True), (RenderMode.PREVIEW, False)):
        context = PageContext(page=view, site=SITE, mode=mode, analytics=analytics)
        html = Renderer(theme, strict=True).render_page(context)
        assert ("data-matomo-url" in html) is expected
