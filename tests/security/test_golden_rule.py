"""Guardiani aggiuntivi della regola d'oro (review Fase 0).

`test_template_lock.py` cerca "theme" e una scrittura sulla stessa riga: si aggira mettendo il
percorso in una variabile. Qui vietiamo le scritture su filesystem in tutto `app/` (salvo
un'allowlist motivata) e verifichiamo a runtime che `themes/` non cambi.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from app import create_app
from app.cli import check_all_themes

ROOT = Path(__file__).resolve().parents[2]
APP_DIR = ROOT / "app"
THEMES_DIR = ROOT / "themes"

WRITE_METHODS = {
    "write_text",
    "write_bytes",
    "mkdir",
    "makedirs",
    "unlink",
    "rmdir",
    "rmtree",
    "touch",
    "symlink_to",
    "hardlink_to",
    "remove",
    "rename",
    "copy",
    "copyfile",
    "copytree",
    "move",
    "save",
}
# (file relativo ad app/, metodo): ogni voce va motivata.
WRITE_ALLOWLIST = {
    ("database.py", "mkdir"),  # crea la cartella del file SQLite da DATABASE_URL (mai themes/)
}
TEMPLATE_CONSTRUCTS = {
    "render_template_string",
    "from_string",
    "Template",
    "Environment",
    "SandboxedEnvironment",
    "compile_expression",
}
# Dalla Fase 3 il solo Environment legittimo (services/render.py) andrà aggiunto qui.
TEMPLATE_ALLOWLIST: set[tuple[str, str]] = set()


def _calls(path: Path) -> list[tuple[str, ast.Call]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            found.append((name, node))
    return found


def _is_write_mode(call: ast.Call) -> bool:
    """`open(..., "w"/"a"/"x"/"+")`, oppure con un mode non letterale (non verificabile)."""
    modes = list(call.args[1:2]) + [k.value for k in call.keywords if k.arg == "mode"]
    for mode in modes:
        literal = mode.value if isinstance(mode, ast.Constant) else None
        if not isinstance(literal, str) or set(literal) & set("wax+"):
            return True
    return False


def _python_files() -> list[Path]:
    return sorted(APP_DIR.rglob("*.py"))


def test_no_filesystem_writes_in_app_outside_allowlist() -> None:
    offenders = []
    for path in _python_files():
        rel = path.relative_to(APP_DIR).as_posix()
        for name, call in _calls(path):
            forbidden = name in WRITE_METHODS and (rel, name) not in WRITE_ALLOWLIST
            if forbidden or (name == "open" and _is_write_mode(call)):
                offenders.append(f"app/{rel}:{call.lineno}: {ast.unparse(call)}")
    assert not offenders, f"Scritture su filesystem non autorizzate: {offenders}"


def test_no_template_construction_from_code() -> None:
    offenders = []
    for path in _python_files():
        rel = path.relative_to(APP_DIR).as_posix()
        offenders += [
            f"app/{rel}:{call.lineno}: {ast.unparse(call)}"
            for name, call in _calls(path)
            if name in TEMPLATE_CONSTRUCTS and (rel, name) not in TEMPLATE_ALLOWLIST
        ]
    assert not offenders, f"Costruzione di template vietata (SSTI): {offenders}"


def _themes_hash() -> str:
    h = hashlib.sha256()
    for p in sorted(THEMES_DIR.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(THEMES_DIR).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def test_themes_unchanged_after_startup_and_theme_check() -> None:
    before = _themes_hash()
    app = create_app("testing")
    app.test_cli_runner().invoke(args=["theme-check"])
    check_all_themes(THEMES_DIR)
    assert _themes_hash() == before


def test_no_safe_filter_in_any_theme_template() -> None:
    offenders = []
    for pattern in ("*.html", "*.jinja", "*.j2", "*.xml", "*.txt"):
        for p in THEMES_DIR.rglob(pattern):
            text = p.read_text(encoding="utf-8").replace(" ", "").replace("|safe_html", "")
            if "|safe" in text:
                offenders.append(str(p.relative_to(ROOT)))
    assert not offenders, f"Filtro |safe vietato: {offenders}"
