"""Guardiano della regola d'oro: il template non è modificabile dal pannello.

Questi test devono restare verdi per sempre. Se un test va in conflitto
con una feature, è la feature a essere sbagliata.
Alcuni test sono marcati `skip` finché la fase corrispondente non esiste:
vanno attivati quando la relativa route viene creata.
"""
from __future__ import annotations

import ast
import hashlib
import io
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP_DIR = ROOT / "app"
THEMES_DIR = ROOT / "themes"

FORBIDDEN_TEMPLATE_CALLS = {"render_template_string", "from_string"}
FORBIDDEN_UPLOAD_EXT = [".html", ".htm", ".jinja", ".j2", ".css", ".js", ".svg", ".php", ".py"]
ALLOWED_SETTING_TYPES = {"text", "textarea", "boolean", "select", "color", "url", "media"}


def _python_files():
    return [p for p in APP_DIR.rglob("*.py")] if APP_DIR.exists() else []


def _themes_hash() -> str:
    h = hashlib.sha256()
    for p in sorted(THEMES_DIR.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(THEMES_DIR)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


# --- Analisi statica -------------------------------------------------------

def test_no_dynamic_template_rendering_in_app():
    """Nessun template costruito da stringhe (rischio SSTI)."""
    offenders = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if name in FORBIDDEN_TEMPLATE_CALLS:
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert not offenders, f"Rendering dinamico vietato: {offenders}"


def test_app_code_never_writes_into_themes():
    """Nessun riferimento a 'themes' accanto a operazioni di scrittura."""
    write_pattern = re.compile(r"(write_text|write_bytes|open\([^)]*['\"][wa]|shutil\.|os\.rename|os\.remove|\.save\()")
    offenders = []
    for path in _python_files():
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "theme" in line.lower() and write_pattern.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{i}: {line.strip()}")
    assert not offenders, f"Possibile scrittura nel tema: {offenders}"


def test_no_jinja_safe_filter_in_themes():
    """I temi usano |safe_html (che ri-sanitizza), mai |safe."""
    offenders = []
    for p in THEMES_DIR.rglob("*.html"):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\|\s*safe\b(?!_html)", line):
                offenders.append(f"{p.relative_to(ROOT)}:{i}")
    assert not offenders, f"Filtro |safe vietato: {offenders}"


def test_theme_settings_are_typed_and_safe():
    import json

    for tj in THEMES_DIR.glob("*/theme.json"):
        data = json.loads(tj.read_text(encoding="utf-8"))
        for key, spec in data.get("settings", {}).items():
            assert spec.get("type") in ALLOWED_SETTING_TYPES, f"{tj}: setting '{key}' di tipo non ammesso"
            assert not re.search(r"(css|js|script|html|code)", key, re.I), f"{tj}: setting '{key}' sospetta"


# --- Test runtime (attivare con le fasi) -----------------------------------

@pytest.fixture
def client():
    app_module = pytest.importorskip("app")
    app = app_module.create_app("testing")
    with app.test_client() as c:
        yield c


@pytest.fixture
def owner_client(client):
    """Client loggato come owner: il ruolo più alto non deve comunque poter toccare il tema."""
    pytest.skip("Attivare in Fase 1: implementare login owner nel fixture")


@pytest.mark.parametrize("ext", FORBIDDEN_UPLOAD_EXT)
def test_media_upload_rejects_renderable_files(owner_client, ext):
    before = _themes_hash()
    payload = b"<script>alert(1)</script>{{ config }}"
    resp = owner_client.post(
        "/api/admin/media",
        data={"file": (io.BytesIO(payload), f"evil{ext}")},
        content_type="multipart/form-data",
    )
    assert resp.status_code in (400, 415, 422)
    assert _themes_hash() == before


def test_media_upload_rejects_disguised_svg(owner_client):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    resp = owner_client.post(
        "/api/admin/media",
        data={"file": (io.BytesIO(svg), "photo.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code in (400, 415, 422)


def test_no_admin_route_touches_theme_files(client):
    app = client.application
    for rule in app.url_map.iter_rules():
        r = rule.rule.lower()
        if r.startswith("/api/admin"):
            assert "theme" not in r or rule.methods <= {"GET", "HEAD", "OPTIONS"}, (
                f"Route admin mutante sul tema: {rule.rule} {rule.methods}"
            )


def test_jinja_in_content_is_not_executed(owner_client):
    """Un blocco testo con sintassi Jinja deve uscire come testo, non essere eseguito."""
    pytest.skip("Attivare in Fase 3: creare pagina con blocco text '{{ 7*7 }}' e verificare che '49' non compaia")


def test_unknown_theme_setting_rejected(owner_client):
    # Route su "appearance" e non "theme": vedi D-14 e test_no_admin_route_touches_theme_files.
    resp = owner_client.put("/api/admin/settings/appearance", json={"custom_css": "body{display:none}"})
    assert resp.status_code in (400, 422)


def test_theme_files_unchanged_after_full_admin_session(owner_client):
    pytest.skip("Attivare in Fase 6: eseguire CRUD completo su pagine/widget/menu/settings e confrontare _themes_hash()")
