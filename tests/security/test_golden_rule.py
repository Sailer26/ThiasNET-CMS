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
    # Archivio dei media (D-74): solo in MEDIA_ROOT, che la configurazione tiene lontana da
    # themes/ e app/, con nomi generati e ricontrollati dopo resolve().
    ("services/media_storage.py", "mkdir"),
    ("services/media_storage.py", "open"),
    ("services/media_storage.py", "unlink"),
    ("services/media_storage.py", "rmdir"),
    # Pillow: l'unica Image.save scrive in un io.BytesIO (test qui sotto).
    ("services/media_images.py", "save"),
}
TEMPLATE_CONSTRUCTS = {
    "render_template_string",
    "render_template",  # l'Environment di Flask non è in sandbox ed espone config (D-52)
    "from_string",
    "Template",
    "Environment",
    "SandboxedEnvironment",
    "ImmutableSandboxedEnvironment",
    "NativeEnvironment",
    "compile_expression",
    "DictLoader",
    "FunctionLoader",
    "FileSystemLoader",
    "PackageLoader",
    "ChoiceLoader",
    "PrefixLoader",
    "ThemeLoader",
}
# Il solo motore dei template legittimo (D-52): sandbox + loader limitato al tema attivo.
TEMPLATE_ALLOWLIST: set[tuple[str, str]] = {
    ("services/render.py", "ImmutableSandboxedEnvironment"),
    ("services/render.py", "ThemeLoader"),
}


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
            allowed_open = (rel, "open") in WRITE_ALLOWLIST
            if forbidden or (name == "open" and _is_write_mode(call) and not allowed_open):
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


SKIPPED_UNTIL_ROUTE = {
    "test_media_upload_rejects_renderable_files": ("/api/admin/media", "POST"),
    "test_media_upload_rejects_disguised_svg": ("/api/admin/media", "POST"),
    "test_unknown_theme_setting_rejected": ("/api/admin/settings/appearance", "PUT"),
}


def test_skipped_lock_tests_have_no_route_yet() -> None:
    """Uno skip del kit non può sopravvivere alla fase in cui nasce la sua route."""
    from tests.security import test_template_lock as kit

    app = create_app("testing")
    routes = {(r.rule, m) for r in app.url_map.iter_rules() for m in (r.methods or ())}
    stale = []
    for name, (path, method) in SKIPPED_UNTIL_ROUTE.items():
        marks = getattr(getattr(kit, name), "pytestmark", [])
        if any(m.name == "skip" for m in marks) and (path, method) in routes:
            stale.append(f"{name}: la route {method} {path} esiste, togliere lo skip")
    assert not stale, stale


def test_no_safe_filter_in_any_theme_template() -> None:
    offenders = []
    for pattern in ("*.html", "*.jinja", "*.j2", "*.xml", "*.txt"):
        for p in THEMES_DIR.rglob(pattern):
            text = p.read_text(encoding="utf-8").replace(" ", "").replace("|safe_html", "")
            if "|safe" in text:
                offenders.append(str(p.relative_to(ROOT)))
    assert not offenders, f"Filtro |safe vietato: {offenders}"


# --- Sito pubblico (Fase 3) ---------------------------------------------------------------

READ_ONLY = {"GET", "HEAD", "OPTIONS"}
# Ogni route fuori da /api, con i metodi che scrivono. Una route nuova va aggiunta qui di
# proposito, dopo averne valutato i rischi.
EXPECTED_PUBLIC_ROUTES = {
    "/": set(),
    "/<path:path>": set(),
    "/assets/<path:filename>": set(),
    "/_vars.css": set(),
    "/sitemap.xml": set(),
    "/robots.txt": set(),
    "/static/<path:filename>": set(),
    "/_preview/<int:page_id>": {"POST"},  # anteprima live: nessuna scrittura (D-55)
    "/_contact": {"POST"},  # modulo contatti (D-61)
}


def test_public_routes_are_known() -> None:
    app = create_app("testing")
    found = {
        rule.rule: set(rule.methods or ()) - READ_ONLY
        for rule in app.url_map.iter_rules()
        if not rule.rule.startswith("/api/")
    }
    assert found == EXPECTED_PUBLIC_ROUTES


def test_themes_unchanged_after_every_public_route() -> None:
    from app.extensions import db

    before = _themes_hash()
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    client = app.test_client()
    for path in (
        "/",
        "/x",
        "/de/",
        "/assets/css/site.css",
        "/_vars.css",
        "/sitemap.xml",
        "/robots.txt",
        "/_preview/1",
    ):
        client.get(path)
    client.post("/_contact", data={"token": "x"})
    assert _themes_hash() == before


def test_media_images_writes_only_to_memory() -> None:
    """L'eccezione per `save` vale solo se scrive in un BytesIO e il modulo non tocca file."""
    path = APP_DIR / "services" / "media_images.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    saves = [call for name, call in _calls(path) if name == "save"]
    assert len(saves) == 1
    assert isinstance(saves[0].args[0], ast.Name) and saves[0].args[0].id == "buffer"
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not imported & {"os", "shutil", "pathlib", "tempfile"}
    for name, call in _calls(path):  # si aprono solo byte già in memoria
        if name == "open":
            source = call.args[0] if call.args else None
            assert isinstance(source, ast.Call) and getattr(source.func, "attr", "") == "BytesIO"
