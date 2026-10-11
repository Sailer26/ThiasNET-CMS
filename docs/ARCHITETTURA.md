# Architettura — ThiasCMS

## Visione d'insieme
```
Browser visitatore ──► Caddy ──► gunicorn/Flask ──► public/ (Jinja SSR dal tema) ──► cache
Browser admin     ──► Caddy ──► /admin (React SPA statica) ──► /api/admin/* (JSON, sessione + CSRF)
                                         │
                         services/ ──► SQLAlchemy ──► SQLite/PostgreSQL
                                   └─► storage media (filesystem / S3-compatibile)
themes/<nome>/  ← SOLO LETTURA a runtime, montato read-only nel container
```

## Moduli backend (`app/`)
| Modulo | Responsabilità |
|---|---|
| `models/` | Tabelle SQLAlchemy |
| `services/pages.py` | CRUD pagine, albero, pubblicazione, revisioni |
| `services/blocks.py` | registry blocchi, validazione JSON Schema, sanitizzazione |
| `services/media.py` | upload, verifica MIME reale, re-encode, varianti, focal point |
| `services/widgets.py` · `menus.py` · `collections.py` | come da nome |
| `services/theme.py` | carica e valida `theme.json` all'avvio; espone zone, blocchi ammessi, settings. **Nessun metodo di scrittura.** |
| `services/render.py` | rendering pagina: layout del tema + blocchi + widget; ambiente Jinja con loader limitato a `themes/<attivo>/` |
| `services/audit.py` | audit log |
| `api/admin/` | blueprint JSON per il pannello (route sottili) |
| `public/` | blueprint del sito: risoluzione slug, redirect, sitemap, robots |

## Modello dati (essenziale)
```
users(id, email, password_hash, role[owner|admin|editor], totp_secret, active, last_login)
pages(id, parent_id, locale, translation_group, slug, path, title, layout, status[draft|published|scheduled],
      publish_at, seo_json, sort, created_by, updated_at)
page_revisions(id, page_id, snapshot_json, author_id, created_at)
blocks(id, page_id, zone, type, data_json, sort)
collections(id, key)            -- dichiarate dal tema, sincronizzate all'avvio
entries(id, collection_id, locale, slug, title, fields_json, status, publish_at)
media(id, folder_id, filename, mime, width, height, sha256, alt, focal_x, focal_y, variants_json)
media_folders(id, parent_id, name)
widgets(id, type, title, data_json, area, sort, visibility_json)
menus(id, location, locale) · menu_items(id, menu_id, parent_id, label, target_type, target_id, url, sort)
settings(key, value_json)       -- sito + settings esposti dal tema
redirects(id, from_path, to_path, code)
audit_log(id, user_id, action, entity, entity_id, diff_json, ip, created_at)
```

## Blocchi
Ogni tipo di blocco = 3 pezzi con lo stesso nome:
1. `app/blocks/<tipo>.schema.json` — JSON Schema dei dati (validato server-side con `jsonschema`).
2. `themes/<tema>/blocks/<tipo>.html` — rendering (scritto da Thias, mai dall'utente).
3. `admin/src/blocks/<tipo>/Editor.tsx` — form di editing.
Riferimenti a media salvati come `media_id`, mai come URL liberi.

## Rendering pubblico
1. Risolvi `path` → pagina pubblicata (o redirect / 404 del tema).
2. Carica layout dichiarato in `theme.json`, blocchi per zona, widget per area, menu.
3. Render con `SandboxedEnvironment`, autoescape ON, `FileSystemLoader` solo su `themes/<attivo>/`.
4. Cache HTML per path+locale; invalidazione su pubblicazione / modifica widget / menu / settings.

## Sicurezza (difesa in profondità per il lock del template)
- Container: `themes/` montato `:ro`; l'utente del processo non ha permessi di scrittura.
- Codice: `services/theme.py` senza metodi di scrittura; nessuna route accetta path di file.
- Upload: allowlist MIME verificata sui byte (jpg, png, webp, gif, pdf); SVG rifiutati; immagini re-encodate con Pillow; nomi file rigenerati; storage fuori da `themes/` e da `static/` del codice.
- Input: JSON Schema + nh3; i dati dei blocchi non sono mai interpretati come template.
- Settings tema: solo chiavi dichiarate in `theme.json`, tipi validati (colore = regex hex, ecc.), nessun campo CSS/JS libero.
- CSP restrittiva sul sito e sull'admin; cookie `Secure`, `HttpOnly`, `SameSite=Lax`.
- Test automatici in `tests/security/test_template_lock.py`.

## Deploy
- `Dockerfile` multi-stage (build admin con Node → runtime Python slim).
- `docker-compose.yml`: app + Caddy; volumi `data/` (db), `media/`; `themes/` copiato nell'immagine (quindi cambia solo con nuovo build).
- Backup notturno DB + media (script `scripts/backup.sh`).
