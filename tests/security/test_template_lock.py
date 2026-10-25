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
import json
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
    write_pattern = re.compile(
        r"(write_text|write_bytes|open\([^)]*['\"][wa]|shutil\.|os\.rename|os\.remove|\.save\()"
    )
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
            assert spec.get("type") in ALLOWED_SETTING_TYPES, (
                f"{tj}: setting '{key}' di tipo non ammesso"
            )
            assert not re.search(r"(css|js|script|html|code)", key, re.I), (
                f"{tj}: setting '{key}' sospetta"
            )


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
    from app.extensions import db
    from tests.helpers import ME_URL, adopt_csrf, make_user, refresh_csrf

    app = client.application
    with app.app_context():
        db.create_all()  # solo nei test (CLAUDE.md)
    owner = make_user(app, "owner@example.ch", "owner")
    refresh_csrf(client)
    resp = client.post(
        "/api/admin/auth/login", json={"email": owner.email, "password": owner.password}
    )
    assert resp.status_code == 200, resp.get_json()
    adopt_csrf(client, resp)
    assert client.get(ME_URL).status_code == 200
    return client


# Skip mirati: la route non esiste ancora. test_golden_rule.py fallisce se la route compare
# mentre lo skip è ancora presente, così lo skip non sopravvive alla sua fase.
SKIP_UNTIL_SETTINGS = pytest.mark.skip(
    reason="Attivare in Fase 6: route /api/admin/settings/appearance assente"
)


def test_owner_client_is_really_logged_in(owner_client):
    me = owner_client.get("/api/admin/auth/me").get_json()["data"]
    assert me["role"] == "owner"


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
    jinja = "{{ 7*7 }}"
    created = owner_client.post(
        "/api/admin/pages", json={"title": jinja, "layout": "page", "slug": "prova"}
    )
    assert created.status_code == 201, created.get_json()
    page_id = created.get_json()["data"]["id"]
    blocks = [
        {"uid": "1" * 32, "type": "text", "data": {"body": f"<p>{jinja}</p>"}},
        {"uid": "2" * 32, "type": "heading", "data": {"text": jinja}},
        {"uid": "3" * 32, "type": "quote", "data": {"text": jinja}},
    ]
    document = {
        "version": 1,
        "title": jinja,
        "layout": "page",
        "seo": {"title": jinja, "description": jinja},
        "zones": {"main": blocks, "sidebar": []},
    }
    assert owner_client.put(f"/api/admin/pages/{page_id}/draft", json=document).status_code == 200
    published = owner_client.post(f"/api/admin/pages/{page_id}/publish", json={"draft_version": 2})
    assert published.status_code == 200, published.get_json()
    html = owner_client.get("/prova").get_data(as_text=True)
    assert "49" not in html
    assert html.count(jinja) >= 5


def test_unknown_theme_setting_rejected(owner_client):
    # Route su "appearance" e non "theme": vedi D-14 e test_no_admin_route_touches_theme_files.
    resp = owner_client.put(
        "/api/admin/settings/appearance", json={"custom_css": "body{display:none}"}
    )
    assert resp.status_code in (400, 422)


def test_theme_files_unchanged_after_full_admin_session(owner_client):
    """Una sessione completa dal pannello non cambia un byte dei temi. Pagine, media e
    impostazioni (6a), menu (6b) e widget (6c)."""
    before = _themes_hash()
    api = "/api/admin"
    page = owner_client.post(f"{api}/pages", json={"title": "Prova", "layout": "page"}).get_json()[
        "data"
    ]
    draft = owner_client.get(f"{api}/pages/{page['id']}/draft").get_json()["data"]
    body = {
        "version": draft["version"],
        "title": "Prova {{ config }}",
        "layout": "page",
        "seo": {"description": "<script>x</script>"},
        "zones": {"main": [], "sidebar": []},
    }
    assert owner_client.put(f"{api}/pages/{page['id']}/draft", json=body).status_code == 200
    version = owner_client.get(f"{api}/pages/{page['id']}/draft").get_json()["data"]["version"]
    published = owner_client.post(
        f"{api}/pages/{page['id']}/publish", json={"draft_version": version}
    )
    assert published.status_code == 200
    upload = owner_client.post(
        f"{api}/media",
        data={"file": (io.BytesIO(_png_bytes()), "foto.png"), "alt": "Foto"},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201, upload.get_json()
    settings = owner_client.get(f"{api}/settings").get_json()["data"]
    logo = upload.get_json()["data"]["id"]
    site = {
        "version": settings["site"]["version"],
        "values": {"name": "Sito {{ 7*7 }}", "logo": logo},
    }
    assert owner_client.put(f"{api}/settings/site", json=site).status_code == 200
    look = {
        "version": settings["appearance"]["version"],
        "values": {"footer_note": "{% include 'x' %}"},
    }
    assert owner_client.put(f"{api}/settings/appearance", json=look).status_code == 200
    menu_items = [
        {"uid": "a" * 32, "url": "/pagina-{{7*7}}", "label": "{% include 'x' %}", "children": []}
    ]
    stored_menu = owner_client.put(f"{api}/menus/main", json={"version": 0, "items": menu_items})
    assert stored_menu.status_code == 200, stored_menu.get_json()
    footer = [
        {
            "uid": "b" * 32,
            "type": "text",
            "data": {
                "title": "Widget {{ 7*7 }}",
                "body": "<p>{% include 'x' %}</p><script>x</script>",
            },
        }
    ]
    stored_footer = owner_client.put(f"{api}/widgets/footer", json={"version": 0, "items": footer})
    assert stored_footer.status_code == 200, stored_footer.get_json()
    notice = [
        {
            "uid": "c" * 32,
            "type": "notice",
            "data": {"text": "{{ config }}", "link_url": "javascript:x"},
        }
    ]
    rejected = owner_client.put(f"{api}/widgets/header_top", json={"version": 0, "items": notice})
    assert rejected.status_code == 422  # link non sicuro
    html = owner_client.get(page["path"]).get_data(as_text=True)
    assert "Widget {{ 7*7 }}" in html and "<script>x</script>" not in html
    _entry_session(owner_client, api)
    page_now = owner_client.get(f"{api}/pages/{page['id']}").get_json()["data"]
    trashed = owner_client.delete(
        f"{api}/pages/{page['id']}", json={"version": page_now["version"]}
    )
    assert trashed.status_code == 200
    assert _themes_hash() == before


def _entry_session(client, api: str) -> None:
    """Notizie (7a): pagina elenco, notizia con Jinja nei campi, campi non previsti rifiutati."""
    listing = client.post(f"{api}/pages", json={"title": "Notizie", "layout": "news_list"})
    assert listing.status_code == 201, listing.get_json()
    listing_id = listing.get_json()["data"]["id"]
    version = client.get(f"{api}/pages/{listing_id}/draft").get_json()["data"]["version"]
    published = client.post(f"{api}/pages/{listing_id}/publish", json={"draft_version": version})
    assert published.status_code == 200
    created = client.post(f"{api}/collections/news/entries", json={"title": "Festa {{ 7*7 }}"})
    entry_id = created.get_json()["data"]["id"]
    draft_url = f"{api}/entries/{entry_id}/draft"
    fields = {"date": "2026-10-24", "body": "<p>{% include 'x' %}</p><script>x</script>"}
    document = {"title": "Festa {{ 7*7 }}", "fields": fields, "seo": {}}
    saved = client.put(draft_url, json={"version": 1, **document})
    assert saved.status_code == 200, saved.get_json()
    evil = {**document, "fields": {**fields, "template": "{{ config }}"}}
    assert client.put(draft_url, json={"version": 2, **evil}).status_code == 422
    css = {**document, "seo": {"custom_css": "body{display:none}"}}
    assert client.put(draft_url, json={"version": 2, **css}).status_code == 422
    publish = client.post(f"{api}/entries/{entry_id}/publish", json={"draft_version": 2})
    assert publish.status_code == 200, publish.get_json()
    html = client.get("/notizie/festa-7-7").get_data(as_text=True)
    assert "Festa {{ 7*7 }}" in html and "<script>x</script>" not in html
    assert client.get("/notizie?p={{7*7}}").status_code == 404
    # 7b: anteprima, versioni e "ultime notizie" restano solo dati
    posted = {"title": "Anteprima {{ 7*7 }}", "fields": fields, "seo": {}}
    shown = client.post(
        f"/_preview/entries/{entry_id}", data={"document": json.dumps(posted)}
    ).get_data(as_text=True)
    assert "Anteprima {{ 7*7 }}" in shown and "<script>x</script>" not in shown
    revision = client.get(f"{api}/entries/{entry_id}/revisions").get_json()["data"][0]
    restore = client.post(
        f"{api}/entries/{entry_id}/revisions/{revision['id']}/restore", json={"draft_version": 0}
    )
    assert restore.status_code == 200, restore.get_json()
    latest = [{"uid": "d" * 32, "type": "latest_entries", "data": {"title": "{{ config }}"}}]
    sidebar = client.put(f"{api}/widgets/sidebar", json={"version": 0, "items": latest})
    assert sidebar.status_code == 200, sidebar.get_json()


def _png_bytes() -> bytes:
    from tests.media_fixtures import image_bytes

    return image_bytes(size=(64, 64))
