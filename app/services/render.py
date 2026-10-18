"""Il solo motore dei template dell'app (D-52): Jinja in sandbox, limitato al tema attivo.

- `ImmutableSandboxedEnvironment` con autoescape: un template non tocca l'interno di Python;
- il loader legge solo la cartella del tema e rifiuta file che, risolti, ne escono (symlink);
- ai template arrivano solo dati congelati (render_context) e gli helper qui sotto;
- i nomi dei template si costruiscono da costanti più nomi verificati contro il tema.
Unica eccezione ammessa da `tests/security/test_golden_rule.py`.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from jinja2 import BaseLoader, FileSystemLoader, Template, TemplateNotFound
from jinja2.environment import Environment
from jinja2.sandbox import ImmutableSandboxedEnvironment
from markupsafe import Markup

from app.core_types import BLOCK_TYPES
from app.services import render_helpers
from app.services.public_texts import text
from app.services.render_context import (
    BlockView,
    ContactFormView,
    PageContext,
    RenderMode,
)
from app.services.theme import Theme

log = logging.getLogger("thiasnet.render")
NOT_FOUND_TEMPLATE = "layouts/404.html"
ASSET_EXTENSIONS = frozenset(
    {".css", ".js", ".woff2", ".woff", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico"}
)
DEFAULT_IMAGE_SIZE = "content"


class ThemeLoader(FileSystemLoader):
    """Come FileSystemLoader, ma un file che risolto esce dal tema non esiste (symlink)."""

    def get_source(
        self, environment: Environment, template: str
    ) -> tuple[str, str, Callable[[], bool]]:
        source, filename, uptodate = super().get_source(environment, template)
        root = Path(self.searchpath[0]).resolve()
        if not Path(filename).resolve().is_relative_to(root):
            raise TemplateNotFound(template)
        return source, filename, uptodate


def build_environment(theme_dir: Path) -> ImmutableSandboxedEnvironment:
    """Ambiente puro (senza app): lo usano il sito e `theme-check`."""
    loader: BaseLoader = ThemeLoader([str(theme_dir)], encoding="utf-8", followlinks=False)
    env = ImmutableSandboxedEnvironment(
        loader=loader, autoescape=True, trim_blocks=True, lstrip_blocks=True
    )
    env.filters["safe_html"] = render_helpers.safe_html
    env.filters["clean_url"] = render_helpers.clean_url
    return env


def asset_path_is_valid(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return (
        bool(parts)
        and not path.startswith("/")
        and "\\" not in path
        and all(part not in {"", ".", ".."} and not part.startswith(".") for part in parts)
        and PurePosixPath(path).suffix.lower() in ASSET_EXTENSIONS
    )


class Renderer:
    """Un renderer per tema attivo; tiene in memoria i template compilati e gli hash degli asset."""

    def __init__(self, theme: Theme, *, strict: bool) -> None:
        self.theme = theme
        self.strict = strict  # sviluppo e test: errori del tema subito evidenti (D-56)
        self.env = build_environment(theme.directory)
        self._asset_versions: dict[str, str] = {}

    # --- Template ---------------------------------------------------------------

    def _layout_template(self, layout: str) -> Template:
        if layout not in self.theme.layouts:  # normalize_document lo garantisce già
            raise TemplateNotFound(layout)
        return self.env.get_template(f"layouts/{layout}.html")

    def _block_template(self, block_type: str) -> Template:
        if block_type not in BLOCK_TYPES:
            raise TemplateNotFound(block_type)
        return self.env.get_template(f"blocks/{block_type}.html")

    def render_page(self, context: PageContext) -> str:
        template = self._layout_template(context.page.layout)
        return template.render(_Helpers(self, context).namespace())

    def render_not_found(self, context: PageContext) -> str:
        return self.env.get_template(NOT_FOUND_TEMPLATE).render(_Helpers(self, context).namespace())

    # --- Asset -----------------------------------------------------------------

    def asset_url(self, path: str) -> str:
        """`/assets/<path>?v=<hash>`: cache lunga, il nome cambia quando cambia il file."""
        if not asset_path_is_valid(path):
            return self._problem(f"asset non valido: {path!r}", "")
        version = self._asset_versions.get(path)
        if version is None:
            file = self.theme.directory / "assets" / path
            if not file.is_file():
                return self._problem(f"asset mancante: {path!r}", "")
            version = hashlib.sha256(file.read_bytes()).hexdigest()[:12]
            self._asset_versions[path] = version
        return f"/assets/{path}?v={version}"

    def _problem(self, message: str, fallback: str) -> str:
        if self.strict:
            raise ValueError(message)
        log.warning("tema %s: %s", self.theme.name, message)
        return fallback


class _Helpers:
    """Helper di un singolo rendering: nessuno stato condiviso tra richieste."""

    def __init__(self, renderer: Renderer, context: PageContext) -> None:
        self.renderer = renderer
        self.context = context
        self.locale = context.page.locale

    def namespace(self) -> dict[str, Any]:
        context = self.context
        return {
            "page": context.page,
            "site": context.site,
            "settings": context.settings,
            "preview": context.mode is RenderMode.PREVIEW,
            "breadcrumbs": context.breadcrumbs,
            "cms_head": lambda: render_helpers.head_markup(context),
            "cms_body_end": lambda: render_helpers.body_end_markup(context),
            "cms_text": lambda key: text(str(key), self.locale),
            "render_zone": self.render_zone,
            "zone_has_blocks": self.zone_has_blocks,
            "render_block": self.render_block,
            "img": self.img,
            "media_url": lambda _media_id: None,  # Fase 4 (D-57)
            "asset": self.renderer.asset_url,
            "embed": render_helpers.embed,
            "menu": self.menu,
            "widget_area": lambda _name: (),  # Fase 6 (D-57)
            "contact_form": self.contact_form,
        }

    def zone_has_blocks(self, name: str) -> bool:
        return bool(self.context.page.zones.get(name))

    def render_zone(self, name: str) -> Markup:
        blocks = self.context.page.zones.get(name, ())
        return Markup("\n").join(self.render_block(block) for block in blocks)

    def render_block(self, block: BlockView) -> Markup:
        try:
            template = self.renderer._block_template(block.type)
        except TemplateNotFound:
            log.warning("tema %s: manca blocks/%s.html", self.renderer.theme.name, block.type)
            return Markup("")
        return Markup(template.render({**self.namespace(), "block": block}))  # noqa: S704

    def img(self, media_id: object, size: str = DEFAULT_IMAGE_SIZE, **_attrs: object) -> Markup:
        """Fino alla Fase 4 nessuna immagine sul sito; in anteprima un segnaposto (D-57)."""
        if size not in self.renderer.theme.image_sizes:
            self.renderer._problem(f"img(): formato {size!r} non dichiarato in image_sizes", "")
        if self.context.mode is RenderMode.PREVIEW and media_id:
            return render_helpers.image_placeholder(self.locale)
        return Markup("")

    def menu(self, location: str) -> tuple[Any, ...]:
        return self.context.menu if location == "main" else ()

    def contact_form(self, block: BlockView) -> ContactFormView | None:
        return self.context.forms.get(block.id)


def blank(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return value or {}
