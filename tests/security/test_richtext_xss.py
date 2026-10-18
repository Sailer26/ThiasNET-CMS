"""XSS sul rich text (D-49): il sanitizer e l'API delle bozze non lasciano passare script."""

from __future__ import annotations

import pytest

from app.services.sanitize import clean_rich, is_safe_url

ATTACKS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "<svg onload=alert(1)>",
    '<math><mi xlink:href="javascript:alert(1)">x</mi></math>',
    '<a href="javascript:alert(1)">x</a>',
    '<a href="JaVaScRiPt:alert(1)">x</a>',
    '<a href="java\tscript:alert(1)">x</a>',
    '<a href="&#106;avascript:alert(1)">x</a>',
    '<a href=" javascript:alert(1)">x</a>',
    '<a href="data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==">x</a>',
    '<a href="vbscript:msgbox(1)">x</a>',
    '<a href="//evil.com">x</a>',
    '<a href="/\\evil.com">x</a>',
    '<iframe src="https://evil.com"></iframe>',
    '<object data="x.swf"></object>',
    '<embed src="x.swf">',
    "<style>@import 'https://evil.com/x.css';</style>",
    '<link rel="stylesheet" href="https://evil.com/x.css">',
    '<base href="https://evil.com/">',
    '<meta http-equiv="refresh" content="0;url=https://evil.com">',
    '<form action="https://evil.com"><input name="password"></form>',
    '<p style="background:url(javascript:alert(1))">x</p>',
    '<p onclick="alert(1)">x</p>',
    '<a href="https://example.ch" target="_blank" onmouseover="alert(1)">x</a>',
    '<noscript><p title="</noscript><img src=x onerror=alert(1)>"></noscript>',
    "<!-- <script>alert(1)</script> -->",
    "<scr\x00ipt>alert(1)</script>",
    "<p>non chiuso <strong>grassetto <a href='javascript:alert(1)'>",
]
DANGEROUS = (
    "<script",
    "onerror",
    "onload",
    "onclick",
    "onmouseover",
    "javascript:",
    "vbscript:",
    "data:",
    "<iframe",
    "<object",
    "<embed",
    "<style",
    "<link",
    "<base",
    "<meta",
    "<form",
    "<input",
    "<img",
    "<svg",
    "<math",
    "style=",
    "target=",
    "//evil.com",
    "\\evil.com",
    "<!--",
)


@pytest.mark.parametrize("attack", ATTACKS)
def test_sanitizer_neutralizes_attack(attack: str) -> None:
    cleaned = clean_rich(attack).lower()
    for marker in DANGEROUS:
        assert marker not in cleaned, f"{marker!r} sopravvive in {cleaned!r}"


def test_allowlist_is_kept_intact() -> None:
    html = (
        "<h2>Titolo</h2><h3>Sotto</h3><h4>Ancora</h4><p><strong>g</strong> <em>c</em><br>"
        "riga</p><ul><li>a</li></ul><ol><li>b</li></ol><blockquote>q</blockquote>"
    )
    assert clean_rich(html) == html


def test_disallowed_headings_become_text() -> None:
    assert clean_rich("<h1>Grande</h1><h5>Piccolo</h5>") == "GrandePiccolo"


@pytest.mark.parametrize(
    "href",
    [
        "https://example.ch/a?b=1",
        "http://example.ch",
        "mailto:a@b.ch",
        "tel:+41911234567",
        "/chi-siamo",
        "/",
    ],
)
def test_safe_links_keep_href_and_get_rel(href: str) -> None:
    cleaned = clean_rich(f'<a href="{href}">x</a>')
    assert cleaned == f'<a href="{href}" rel="noopener noreferrer">x</a>'


def test_unsafe_link_keeps_text_without_href() -> None:
    assert clean_rich('<a href="//evil.com">x</a>') == '<a rel="noopener noreferrer">x</a>'


def test_sanitizing_is_idempotent() -> None:
    once = clean_rich('<p>a <a href="/x" rel="nofollow">b</a> <script>c</script></p>')
    assert clean_rich(once) == once


def test_jinja_syntax_stays_literal_text() -> None:
    assert clean_rich("<p>{{ 7*7 }} {% if %}</p>") == "<p>{{ 7*7 }} {% if %}</p>"


@pytest.mark.parametrize(
    ("url", "safe"),
    [
        ("https://example.ch", True),
        ("http://example.ch/path#frag", True),
        ("mailto:info@example.ch", True),
        ("tel:+41911234567", True),
        ("tel:+41 91 123 45 67", False),  # niente spazi negli indirizzi
        ("/pagina", True),
        ("//evil.com", False),
        ("/\\evil.com", False),
        ("javascript:alert(1)", False),
        (" https://example.ch", False),
        ("https://example.ch/\x00", False),
        ("ftp://example.ch", False),
        ("https://" + "a" * 2050, False),
        ("", False),
    ],
)
def test_is_safe_url(url: str, safe: bool) -> None:
    assert is_safe_url(url) is safe


@pytest.mark.parametrize(("url", "safe"), [("#sezione-2", True), ("#", False), ("#a b", False)])
def test_anchors(url: str, safe: bool) -> None:
    assert is_safe_url(url) is safe
