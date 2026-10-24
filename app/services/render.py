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

from jinja2 import BaseLoader, FileSystemLoader, Template, TemplateError, TemplateNotFound
from jinja2.environment import Environment
from jinja2.sandbox import ImmutableSandboxedEnvironment
from markupsafe import Markup

from app.core_types import BLOCK_TYPES, WIDGET_TYPES
from app.services import render_helpers, render_media
from app.services.public_texts import text
from app.services.render_context import (
    BlockView,
    ContactFormView,
    Link,
    MediaView,
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


def build_environment(
    theme_dir: Path, *, auto_reload: bool = True
) -> ImmutableSandboxedEnvironment:
    """Ambiente puro (senza app): lo usano il sito e `theme-check`. In produzione i template
    non cambiano (solo con un deploy): niente controllo dei file a ogni richiesta."""
    loader: BaseLoader = ThemeLoader([str(theme_dir)], encoding="utf-8", followlinks=False)
    env = ImmutableSandboxedEnvironment(
        loader=loader,
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
        auto_reload=auto_reload,
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
        self.env = build_environment(theme.directory, auto_reload=strict)
        self._asset_versions: dict[str, str] = {}

    # --- Template ---------------------------------------------------------------

    def _layout_template(self, layout: str) -> Template:
        if layout not in self.theme.layouts:  # normalize_document lo garantisce già
            raise TemplateNotFound(layout)
        return self.env.get_template(f"layouts/{layout}.html")

    def block_template(self, block_type: str) -> Template:
        if block_type not in BLOCK_TYPES:
            raise TemplateNotFound(block_type)
        return self.env.get_template(f"blocks/{block_type}.html")

    def widget_template(self, widget_type: str) -> Template:
        if widget_type not in WIDGET_TYPES:
            raise TemplateNotFound(widget_type)
        return self.env.get_template(f"widgets/{widget_type}.html")

    def render_page(self, context: PageContext) -> str:
        template = self._layout_template(context.page.layout)
        return template.render(_Helpers(self, context).namespace())

    def render_not_found(self, context: PageContext) -> str:
        return self.env.get_template(NOT_FOUND_TEMPLATE).render(_Helpers(self, context).namespace())

    # --- Asset -----------------------------------------------------------------

    def asset_version(self, path: str) -> str | None:
        """Impronta del contenuto di un file in `assets/` (memorizzata per processo)."""
        if not asset_path_is_valid(path):
            return None
        version = self._asset_versions.get(path)
        if version is None:
            file = self.theme.directory / "assets" / path
            if not file.is_file():
                return None
            version = hashlib.sha256(file.read_bytes()).hexdigest()[:12]
            self._asset_versions[path] = version
        return version

    def asset_url(self, path: str) -> str:
        """`/assets/<path>?v=<hash>`: cache lunga, il nome cambia quando cambia il file."""
        version = self.asset_version(path)
        if version is None:
            return self._problem(f"asset non valido o mancante: {path!r}", "")
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
            "media_url": self.media_url,
            "media_file": self.media_file,
            "asset": self.renderer.asset_url,
            "embed": render_helpers.embed,
            "menu": self.menu,
            "widget_area": self.widget_area,
            "contact_form": self.contact_form,
        }

    def widget_area(self, name: str) -> Markup:
        """I widget di un'area visibili in questa pagina, già disegnati (D-146). Un widget che
        non si riesce a disegnare sparisce (con avviso nel log), come i blocchi (D-53)."""
        found = []
        for widget in self.context.widgets.get(name, ()):
            try:
                template = self.renderer.widget_template(widget.type)
                html = template.render({**self.namespace(), "widget": widget})
            except (TemplateError, TypeError, ValueError, AttributeError):
                if self.renderer.strict:
                    raise
                log.exception(
                    "tema %s: widget %s non disegnato", self.renderer.theme.name, widget.id
                )
                continue
            found.append(Markup(html))  # noqa: S704 (output del template, già escapato)
        return Markup("\n").join(found)

    def zone_has_blocks(self, name: str) -> bool:
        return bool(self.context.page.zones.get(name))

    def render_zone(self, name: str) -> Markup:
        blocks = self.context.page.zones.get(name, ())
        return Markup("\n").join(self.render_block(block) for block in blocks)

    def render_block(self, block: BlockView) -> Markup:
        """Un blocco che non si riesce a disegnare sparisce (con avviso nel log): la pagina
        resta online (D-53). In sviluppo e nei test l'errore si vede subito."""
        try:
            template = self.renderer.block_template(block.type)
            html = template.render({**self.namespace(), "block": block})
        except (TemplateError, TypeError, ValueError, AttributeError):
            if self.renderer.strict:
                raise
            log.exception("tema %s: blocco %s non disegnato", self.renderer.theme.name, block.id)
            return Markup("")
        return Markup(html)  # noqa: S704 (output del template, già escapato)

    def _media(self, media_id: object) -> MediaView | None:
        if isinstance(media_id, bool) or not isinstance(media_id, int):
            return None
        return self.context.media.get(media_id)

    def img(
        self,
        media_id: object,
        size: str = DEFAULT_IMAGE_SIZE,
        sizes: object = None,
        eager: bool = False,
        css_class: object = None,
    ) -> Markup:
        """Immagine responsive (D-81). Media mancante: niente sul sito, segnaposto in anteprima."""
        if size not in self.renderer.theme.image_sizes:
            self.renderer._problem(f"img(): formato {size!r} non dichiarato in image_sizes", "")
        media = self._media(media_id)
        if media is not None and media.kind == "image":
            return render_media.img_markup(
                media, size, sizes=sizes, eager=eager, css_class=css_class
            )
        if media_id:
            log.warning("pagina %s: immagine %r non disponibile", self.context.page.id, media_id)
        if self.context.mode is RenderMode.PREVIEW and media_id:
            return render_helpers.image_placeholder(self.locale)
        return Markup("")

    def media_url(self, media_id: object) -> str | None:
        media = self._media(media_id)
        return media.url if media is not None else None

    def media_file(self, media_id: object) -> Mapping[str, Any] | None:
        """Per i file da scaricare: indirizzo, nome, formato e peso (D-81)."""
        media = self._media(media_id)
        return render_media.file_info(media) if media is not None else None

    def menu(self, location: str) -> tuple[Link, ...]:
        return self.context.menus.get(location, ())

    def contact_form(self, block: BlockView) -> ContactFormView | None:
        return self.context.forms.get(block.id)
