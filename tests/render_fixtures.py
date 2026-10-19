"""Aiuti per i test del rendering: documenti di pagina e contesti pronti."""

from __future__ import annotations

from html.parser import HTMLParser
from types import MappingProxyType
from typing import Any

from app.services.render import Renderer
from app.services.render_context import (
    Link,
    PageContext,
    RenderMode,
    SiteInfo,
    normalize_document,
)
from app.services.theme import Theme

SITE = SiteInfo(name="Comune di Prova", base_url="https://www.example.ch", locale="it", year=2026)


def render_doc(
    theme: Theme,
    document: dict[str, Any],
    *,
    mode: RenderMode = RenderMode.PUBLIC,
    path: str = "/chi-siamo",
    is_home: bool = False,
    menu: tuple[Link, ...] = (),
    renderer: Renderer | None = None,
) -> str:
    view = normalize_document(theme, document, page_id=1, locale="it", path=path, is_home=is_home)
    context = PageContext(page=view, site=SITE, mode=mode, menus=MappingProxyType({"main": menu}))
    return (renderer or Renderer(theme, strict=True)).render_page(context)


class Inspector(HTMLParser):
    """Raccoglie tag, attributi e testo per controllare l'HTML prodotto."""

    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.inline_scripts = 0
        self._in_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))
        self._in_script = tag == "script"

    def handle_endtag(self, tag: str) -> None:
        self._in_script = False

    def handle_data(self, data: str) -> None:
        if self._in_script and data.strip():
            self.inline_scripts += 1

    def find(self, tag: str) -> list[dict[str, str | None]]:
        return [attrs for name, attrs in self.tags if name == tag]


def inspect(html: str) -> Inspector:
    parser = Inspector()
    parser.feed(html)
    return parser
