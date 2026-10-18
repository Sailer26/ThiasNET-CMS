"""Controllo dei template di un tema (D-63), usato da `theme-check`.

Errori: template obbligatori mancanti, template che non si compilano, helper del CMS non
usati (senza `cms_head()` e `cms_body_end()` mancherebbero SEO, consenso e anteprima).
Avvisi: varianti dichiarate per blocchi che nessuna zona ammette.
I template mancanti non bloccano l'avvio dell'app: li ferma la CI (e il build, Fase 8).
"""

from __future__ import annotations

from jinja2 import TemplateSyntaxError

from app.services.render import NOT_FOUND_TEMPLATE, build_environment
from app.services.theme import Theme

REQUIRED_HELPERS = ("cms_head()", "cms_body_end()")
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
    if "contacts" in allowed:
        required.append(CONTACT_FORM_TEMPLATE)
    return required


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
    sources: list[str] = []
    for name in files:
        try:
            env.get_template(name)
        except TemplateSyntaxError as exc:
            errors.append(f"{theme.name}: {name} riga {exc.lineno}: {exc.message}")
        sources.append((theme.directory / name).read_text(encoding="utf-8"))
    errors += [
        f"{theme.name}: nessun template usa {helper}"
        for helper in REQUIRED_HELPERS
        if not any(helper in source for source in sources)
    ]
    warnings = [
        f"{theme.name}: varianti per il blocco {block!r}, che nessuna zona ammette"
        for block in sorted(theme.block_variants)
        if block not in allowed
    ]
    return errors, warnings
