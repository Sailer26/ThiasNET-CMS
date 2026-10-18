# Architettura — ThiasNET CMS

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
| `services/pages.py` · `page_paths.py` · `slugs.py` | CRUD pagine, albero, slug, percorsi e 301, riordino, cestino (D-43, D-45) |
| `services/drafts.py` | bozze autosave con blocco ottimistico, operazioni sui singoli blocchi (D-07, D-44) |
| `services/publishing.py` | pubblica, programma, ritira, `publish_due` per `flask publish-scheduled` (D-16, D-47) |
| `services/revisions.py` | storico, ripristino in bozza, potatura a 50 (D-40, D-42) |
| `services/content.py` | forma del documento pagina e regole del tema (zone, blocchi ammessi, max, varianti) |
| `services/blocks.py` · `sanitize.py` | registry dei 13 schemi, validazione bozza/pubblica, pulizia testo e rich text con nh3 (D-46, D-49) |
| `services/media.py` | upload, verifica MIME reale, re-encode, varianti, focal point |
| `services/widgets.py` · `menus.py` · `collections.py` | come da nome |
| `services/theme.py` | carica e valida `theme.json` all'avvio; espone zone, blocchi ammessi, settings. **Nessun metodo di scrittura.** |
| `services/render.py` | rendering pagina: layout del tema + blocchi + widget; ambiente Jinja con loader limitato a `themes/<attivo>/` |
| `services/audit.py` | audit log |
| `api/admin/` | blueprint JSON per il pannello (route sottili) |
| `public/` | blueprint del sito: risoluzione slug, redirect, sitemap, robots |

## Modello dati (essenziale)
```
users(id, email, password_hash, role[owner|admin|editor], active, can_publish, totp_secret_enc,
      totp_last_counter, session_version, last_login_at, tour_completed_at, created_at, updated_at)
login_attempts(id, email_key, ip_key, created_at)   -- rate limit su DB, solo chiavi HMAC (D-24)
pages(id, parent_id, locale, translation_group, slug, path, title, layout, status[draft|published|scheduled],
      publish_at, published_at, seo_json, sort, version, created_by, updated_by, created_at, updated_at,
      deleted_at, deleted_by)   -- path unico per lingua tra le pagine non cestinate (indice parziale)
page_revisions(id, page_id, kind[published|scheduled|unpublished|draft], snapshot_json, author_id, created_at)
blocks(id, page_id, uid, zone, type, variant, data_json, sort)   -- solo la versione pubblicata (D-38)
page_redirects(id, page_id, locale, from_path, created_at)       -- vecchi indirizzi → 301 dalla Fase 3 (D-45)
collections(id, key)            -- dichiarate dal tema, sincronizzate all'avvio
entries(id, collection_id, locale, slug, title, fields_json, status, publish_at)
media(id, folder_id, filename, mime, width, height, sha256, alt, focal_x, focal_y, variants_json)
media_folders(id, parent_id, name)
widgets(id, type, title, data_json, area, sort, visibility_json)
menus(id, location, locale) · menu_items(id, menu_id, parent_id, label, target_type, target_id, url, sort)
settings(key, value_json)       -- sito + settings esposti dal tema
redirects(id, from_path, to_path, code)
audit_log(id, user_id, action, entity, entity_id, diff_json, ip_hash, created_at)   -- D-30
page_drafts(page_id, data_json, version, author_id, created_at, updated_at)   -- autosave (D-07, D-44)
contact_messages(id, form_page_id, name, email, message, ip_hash, created_at)   -- D-05
support_requests(id, user_id, page_id, message, created_at, sent_at)           -- "Chiedi a Thias" (D-09)
-- users ha in più: can_publish (D-15), tour_completed_at (D-08)
```

## Blocchi
Ogni tipo di blocco = 3 pezzi con lo stesso nome:
1. `app/blocks/<tipo>.schema.json` — JSON Schema dei dati (validato server-side con `jsonschema`).
2. `themes/<tema>/blocks/<tipo>.html` — rendering (scritto da Thias, mai dall'utente).
3. `admin/src/blocks/<tipo>/Editor.tsx` — form di editing.
Riferimenti a media salvati come `media_id`, mai come URL liberi.

Annotazioni negli schemi: `x-richtext` (HTML ripulito con nh3), `x-media` (id di un media),
formato `safe-url` (http(s), mailto, tel o percorso del sito). Ogni oggetto è chiuso
(`additionalProperties: false`) e ogni stringa ha un limite: un meta-test lo verifica.
Due livelli di validazione (D-46): in bozza i campi obbligatori possono mancare, per pubblicare no.

## Pagine: bozza, pubblicazione, revisioni (D-38)
```
autosave ──PUT /draft──► page_drafts.data_json (version+1)        mai pages/blocks
pubblica ──────────────► rivalida col tema attuale → blocks sostituiti → revisione → bozza cancellata
programma ─────────────► revisione "scheduled" (istantanea congelata) + pages.publish_at
flask publish-scheduled ► rivalida l'istantanea; se il tema è cambiato e non è più valida: niente
                          pubblicazione, audit page.schedule_failed, istantanea tenuta come "draft"
```

## Anteprima live (D-02)
- L'editor admin mostra un iframe su `/_preview/<page_id>` (solo utenti loggati, stessa origine, `X-Frame-Options: SAMEORIGIN` solo su questa route).
- Il pannello invia lo stato corrente della bozza con `POST /api/admin/pages/<id>/preview` (validato con gli stessi schemi dei blocchi); il server renderizza con il tema attivo esattamente come il sito pubblico, aggiungendo solo un piccolo script del CMS (file statico, compatibile CSP) che evidenzia i blocchi via `data-block-id` e comunica il click al pannello con `postMessage` (origine verificata).
- Il rendering di anteprima non scrive cache e non pubblica nulla.

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
