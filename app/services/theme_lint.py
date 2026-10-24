"""Controllo dei template di un tema (D-63), usato da `theme-check`.

Errori: template obbligatori mancanti, template che non si compilano o che includono/estendono
file inesistenti, helper del CMS non usati (senza `cms_head()` e `cms_body_end()` mancherebbero
SEO, consenso e anteprima).
Avvisi: varianti dichiarate per blocchi che nessuna zona ammette.
I template mancanti non bloccano l'avvio dell'app: li ferma la CI (e il build, Fase 8).
"""

from __future__ import annotations

from jinja2 import TemplateError, meta, nodes

from app.core_types import ENABLED_WIDGET_TYPES
from app.services.render import NOT_FOUND_TEMPLATE, build_environment
from app.services.theme import Theme

REQUIRED_HELPERS = ("cms_head", "cms_body_end")
CONTACT_FORM_TEMPLATE = "partials/contact_form.html"


def _allowed_blocks(theme: Theme) -> set[str]:
    return {
        block
        for layout in theme.layouts.values()
        for zone in layout.zones.values()
        for block in zone.blocks
    }


def _required_templates(theme: Theme, allowed: set[str]) -> list[str]:
    required = [f"layouts/{name}.html" for name in theme.layouts]
    required.append(NOT_FOUND_TEMPLATE)
    required += [f"blocks/{block}.html" for block in sorted(allowed)]
    used = {w for area in theme.widget_areas.values() for w in area.widgets}
    required += [f"widgets/{widget}.html" for widget in sorted(used & ENABLED_WIDGET_TYPES)]
    required += [f"entries/{key}.html" for key in sorted(theme.collections)]  # dettaglio (D-149)
    if "contacts" in allowed:
        required.append(CONTACT_FORM_TEMPLATE)
    return required


def _called_names(tree: nodes.Template) -> set[str]:
    """Funzioni chiamate davvero (non basta trovarne il nome in un commento)."""
    return {
        call.node.name for call in tree.find_all(nodes.Call) if isinstance(call.node, nodes.Name)
    }


def lint_theme(theme: Theme) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    allowed = _allowed_blocks(theme)
    files = sorted(
        path.relative_to(theme.directory).as_posix()
        for path in theme.directory.rglob("*.html")
        if not path.relative_to(theme.directory).as_posix().startswith("assets/")
    )
    errors += [
        f"{theme.name}: manca il template {name}"
        for name in _required_templates(theme, allowed)
        if name not in files
    ]
    env = build_environment(theme.directory)
    called: set[str] = set()
    for name in files:
        try:
            source = env.loader.get_source(env, name)[0]  # type: ignore[union-attr]
            tree = env.parse(source, name=name)
            env.get_template(name)
        except (TemplateError, UnicodeDecodeError, OSError) as exc:
            line = getattr(exc, "lineno", None)
            where = f" riga {line}" if line else ""
            errors.append(f"{theme.name}: {name}{where}: {exc}")
            continue
        called |= _called_names(tree)
        for referenced in meta.find_referenced_templates(tree):
            if referenced is None:
                errors.append(f"{theme.name}: {name}: include/extends con nome calcolato")
            elif referenced not in files:
                errors.append(f"{theme.name}: {name} usa {referenced}, che non esiste")
    errors += [
        f"{theme.name}: nessun template usa {helper}()"
        for helper in REQUIRED_HELPERS
        if helper not in called
    ]
    warnings = [
        f"{theme.name}: varianti per il blocco {block!r}, che nessuna zona ammette"
        for block in sorted(theme.block_variants)
        if block not in allowed
    ]
    return errors, warnings
