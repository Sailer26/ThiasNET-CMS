# Architettura — ThiasNET CMS

## Visione d'insieme
```
Browser visitatore ──► Caddy ──► gunicorn/Flask ──► public/ (Jinja SSR dal tema) ──► cache
Browser admin     ──► Caddy ──► /admin (React SPA servita da Flask) ──► /api/admin/* (JSON, sessione + CSRF)
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
| `services/media.py` | upload, modifica, "Sostituisci file", eliminazione, spazio per sito, varianti dopo un cambio del tema (D-76 … D-82) |
| `services/media_types.py` · `media_images.py` · `media_storage.py` | tipo del file dai byte (senza Pillow) · decodifica con limiti, pulizia, master e varianti WebP in memoria · unico punto che scrive in `MEDIA_ROOT` (D-70 … D-74) |
| `services/media_refs.py` · `media_library.py` · `media_folders.py` | media usati dalle pagine e controlli di pubblicazione · elenco, ricerca, indirizzi · cartelle |
| `services/render_media.py` | `<img>` responsive, file scaricabili, tag social (D-81) |
| `services/widgets.py` · `menus.py` · `collections.py` | come da nome |
| `services/theme.py` | carica e valida `theme.json` all'avvio; espone zone, blocchi ammessi, settings. **Nessun metodo di scrittura.** |
| `services/render.py` · `render_context.py` · `render_helpers.py` | unico ambiente Jinja in sandbox, loader limitato a `themes/<attivo>/` (anche contro i symlink), dati congelati e helper del contratto (D-52, D-53, D-56) |
| `services/public_pages.py` · `public_render.py` | indirizzi e lingue, redirect 301, menu automatico, percorso; contesto di una pagina per il renderer (D-50, D-51, D-58) |
| `services/page_cache.py` | cache HTML in memoria per processo, generazione condivisa in `site_state` (D-54) |
| `services/seo.py` · `preview.py` · `contact_form.py` · `mailer.py` · `theme_lint.py` | sitemap/robots · anteprima · modulo contatti · email · controllo dei template del tema |
| `services/audit.py` | audit log |
| `api/admin/` | blueprint JSON per il pannello (route sottili) |
| `public/` | blueprint del sito: pagine, asset del tema, `/_vars.css`, sitemap, robots, `/_preview/<id>`, `/_contact`, pagine d'errore |

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
entries(id, collection, locale, translation_group, slug, title, fields_json, seo_json, status, publish_at,
        published_at, sort_at, scheduled_json, scheduled_by, version, created/updated/deleted_*)  -- D-147
        unico (locale, collection, slug) tra le non cestinate; la raccolta è la chiave del tema
entry_drafts(entry_id PK, data_json, version, author_id, created_at, updated_at)
media(id, storage_key, kind[image|document], mime, ext, original_name, search_key, size_bytes, sha256 UNIQUE,
      width, height, alt, focal_x, focal_y, variants_json, file_rev, version, folder_id, created_by, updated_by,
      created_at, updated_at)   -- file in MEDIA_ROOT/<key[:2]>/<key>/r<rev>-..., mai nel database (D-74)
media_folders(id, parent_id, name, name_key)   -- nome unico per cartella madre (indice parziale per la radice)
settings(scope PK 'site'|'appearance', values_json, version, updated_by, updated_at)  -- D-143, D-144
entity_revisions(id, entity_type, entity_key, snapshot_json, author_id, created_at)   -- versioni di impostazioni, menu, widget (D-139)
menus(location, locale, items_json, version, updated_by, updated_at)  PK(location, locale)  -- menu fatti a mano (D-145)
widget_areas(area, locale, items_json, version, next_change_at, updated_by, updated_at)  PK(area, locale)  -- D-146
redirects(id, from_path, to_path, code)
audit_log(id, user_id, action, entity, entity_id, diff_json, ip_hash, created_at)   -- D-30
page_drafts(page_id, data_json, version, author_id, created_at, updated_at)   -- autosave (D-07, D-44)
contact_messages(id, form_page_id, name, email, message, ip_hash, created_at)   -- D-05
support_requests(id, user_id, page_id, screen, message, created_at, sent_at, send_attempts, last_error)  -- "Chiedi a Thias" (D-09, D-134)
-- users ha in più: can_publish (D-15), tour_completed_at (D-08)
```

## Blocchi
Ogni tipo di blocco = 2 pezzi con lo stesso nome, più un aiuto facoltativo (D-112):
1. `app/blocks/<tipo>.schema.json` — JSON Schema dei dati (validato server-side con `jsonschema`), con le
   etichette italiane dei campi (`title`, `description`, `x-enum-titles`): senza, l'app non parte (D-106).
2. `themes/<tema>/blocks/<tipo>.html` — rendering (scritto da Thias, mai dall'utente).
3. Il modulo del pannello si genera dallo schema (`admin/src/features/editor/schema/`); un file a parte
   solo per gli aiuti (video, mappa, contatti) in 5b-2. Il validatore del pannello conosce solo le parole
   chiave elencate in `tests/unit/test_blocks_registry.py` e dà lo stesso verdetto del server sui casi di
   `tests/fixtures/safe_url_cases.json`.
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

## Anteprima live (D-02, D-55)
- L'editor del pannello mostra un iframe su `/_preview/<page_id>` (solo chi ha `content.edit`, agli altri 404; `X-Frame-Options: SAMEORIGIN` e `frame-ancestors 'self'` solo su questa route, `no-store`, `noindex`).
- `GET` mostra la bozza salvata; il pannello invia lo stato corrente con un form `POST /_preview/<page_id>` (campo `document` in JSON + `csrf_token`) con `target` sull'iframe: la risposta è una pagina vera, stessa origine, validata come l'autosave (modalità bozza).
- `app/static/cms/preview.js` (file statico, compatibile CSP) evidenzia i blocchi via `data-block-id`, invia `cms:block-click` al pannello con `postMessage` e accetta `cms:highlight` solo dalla stessa origine e dalla finestra madre.
- L'anteprima non scrive nulla: né bozze, né revisioni, né cache; il modulo contatti è visibile ma disattivato.
- Il pannello crea un iframe nuovo a ogni aggiornamento (500 ms dopo l'ultima modifica) e lo scambia con il
  vecchio quando arriva `cms:ready`: niente voci nella storia del browser (D-107). `cms:highlight` accetta
  `scroll: false`; `preview.js` salva lo scorrimento mentre si scorre. Un CSRF scaduto in anteprima risponde
  con una pagina HTML mostrabile nell'iframe.

## Editor della pagina (5b, D-102 … D-115)
```
EditorScreen ─► GET /pages/<id> + GET /draft (o il pubblicato) + GET /blocks + albero (link interni)
   storia (100 passi) ─► Autosave: PUT /draft dopo 1,5 s, una richiesta alla volta, versione della bozza
   draftSafe: un campo scritto a metà manda l'ultimo valore valido ─► anteprima e salvataggio senza 422
   Pubblica: flush ─► conferma con l'indirizzo ─► POST /publish {draft_version} ─► errori con "Vai al campo"
```
- `admin/src/features/editor/model/`: funzioni pure (documento, cambio del tipo di pagina, storia,
  `draftSafe`, percorsi degli errori) e `Autosave` senza React; l'`uid` dei blocchi lo crea il pannello.
- Testo formattato: TipTap 3 con le sole estensioni di D-49 (`richtext/extensions.ts`), nessun CSS iniettato.
- L'editor è un pezzo separato della build: si scarica solo quando si apre una pagina.

## Media (D-70 … D-85)
```
POST /api/admin/media ─► sniff (magic bytes) ─► Pillow: limiti, EXIF/ICC→sRGB, master + varianti WebP (in memoria)
                       └► media_storage.put (nome generato, creazione esclusiva) ─► riga `media` + audit
GET /media/<key>/<file> ─► solo file della revisione corrente; immagini immutabili, PDF in download
                           con `max-age=300`; `nosniff`, CSP `sandbox`, mai cookie di sessione
```
- `MEDIA_ROOT` sta fuori da `themes/` e da `app/` (controllato all'avvio, obbligatorio in produzione).
- Ogni modifica che cambia i file (punto focale, sostituzione, `flask media-variants`) crea una nuova revisione
  di file: l'indirizzo cambia e la cache dei browser non mostra mai il file vecchio. Il master non si ricodifica.
- "In uso" (D-79): blocchi e SEO di tutte le pagine non cestinate, bozze e programmazioni. Un media in uso non si
  elimina (409 con l'elenco delle pagine); l'alt non si toglie se una pagina online o programmata lo usa.
- Pubblicare verifica che ogni `media_id` esista, sia del tipo giusto (immagine o PDF) e abbia l'alt.

## Pannello (D-86 … D-99)
```
admin/ (Vite + React + TS) ──npm run build──► admin/dist (ADMIN_DIST_DIR, mai in themes/ o app/)
GET /admin/<qualsiasi>      ──► index.html (file statico, no-cache, CSP del pannello, X-Frame-Options DENY)
GET /admin/assets/<file>    ──► solo .js/.css/.woff2/.png esistenti nella build, cache di un anno
SPA ──fetch──► /api/admin/* (cookie di sessione SameSite=Strict + header X-CSRFToken)
```
- `app/panel.py` (route) e `app/services/panel_assets.py` (percorsi, CSP); nessun Jinja, solo GET.
- `admin/src/api/client.ts` è l'unico punto delle chiamate: busta `{success, data, error, meta}`, token CSRF
  solo in memoria, un nuovo tentativo dopo un 403 `csrf`, evento di sessione scaduta solo sui 401
  `unauthorized` (D-90, D-127): password o codice sbagliati restano errori del modulo.
- `admin/src/session/` apre una finestra di nuovo accesso sopra lo schermo; se entra un altro utente il
  pannello si ricarica da capo. Nessun timer verso l'API.
- `admin/src/features/page-tree/tree.ts` contiene le regole dell'albero (profondità, destinazioni, ordine)
  come funzioni pure; il server ricontrolla tutto.
- `admin/src/features/admin/` (5c-2): Messaggi, Utenti, Registro, Profilo. Il menu e le rotte seguono i
  permessi della sessione (`session/can.ts`); un indirizzo senza permesso mostra "Non hai accesso" e non chiama
  l'API (D-130). Il numero dei messaggi da leggere è un piccolo store (`unread.ts`) letto all'avvio, quando la
  finestra torna visibile e dopo ogni azione, mai con un timer. Gli elenchi controllano la forma della risposta.
- 5d-1: `GET /pages/<id>/checks` (`app/services/prepublish.py`) usa la stessa validazione di `publish`
  (`publishing.problems`) e controlla i link con `public_pages.resolve(..., publish_due=False)`, che non scrive
  nulla; la conferma di pubblicazione mostra gli avvisi (`WarningList`) e sul telefono `PhonePublish`.
  `POST /support-requests` (`app/services/support.py`): salva, poi email a `SUPPORT_EMAIL` della configurazione;
  `flask send-support-requests` / `purge-support-requests` da cron come per i messaggi.
- 5d-2: `admin/src/features/help/` (tour `Tour.tsx` con passi in `text/help.ts` e `data-tour` sugli elementi,
  `HelpMenu.tsx`, `AskThias.tsx`); `POST /auth/me/tour` segna il tour una volta sola.
- 6a: `GET /settings`, `PUT /settings/site`, `PUT /settings/appearance` (`settings.edit`, admin e owner).
  `settings_fields.py` dà schema (per `SchemaForm` del pannello, con `x-color` per la palette) e validazione;
  `settings_store.py` salva con versione, registro, versioni e `mark_changed()`; `site_settings.current()` e
  `theme_settings()` leggono dal database (cache per richiesta in `g`).
- 6b: `GET /menus`, `PUT`/`DELETE /menus/<posizione>` (`content.publish`); `app/services/menus.py` valida l'albero
  (senza ricorsione sul conteggio), salva con versione e dà al rendering `site_menus()` (un `Link` con `children`
  per posizione); pannello in `admin/src/features/menus/` (operazioni pure in `tree.ts`).
- 6c: `GET /widgets`, `GET`/`PUT /widgets/<area>` (`content.publish`); `app/services/widgets.py` valida con gli
  schemi di `app/widgets/` (lo stesso `BlockRegistry` dei blocchi), salva con versione e dà al rendering
  `site_widgets()` (i `WidgetView` visibili per area); `expire_due()` rinnova la cache quando scade un banner
  (route pubblica e `publish-scheduled`). Pannello in `admin/src/features/widgets/` (operazioni pure in `model.ts`).
- 7b: `GET /entries/<id>/checks`, `GET /entries/<id>/revisions/<rid>` e `/restore`; anteprima `/_preview/entries/<id>`;
  `site` con `collections`; nel pannello `admin/src/features/entries/` (elenco, editor, telefono) sopra i pezzi
  comuni di `features/editor/` (`Autosave` e `History` generici, `useAutosaveLifecycle`, `ConflictDialog`, `SeoFields`,
  `undoKeys`, `PreviewPane` con `action`).
- 7a: `GET /collections`, `GET`/`POST /collections/<chiave>/entries`, `GET`/`PATCH`/`DELETE /entries/<id>` e
  `/restore`, `/draft`, `/publish`, `/schedule`, `/unschedule`, `/unpublish`, `/revisions` (`content.edit`, le azioni
  su voci online chiedono `content.publish`). `collections.py` genera lo schema dei campi dal tema e lo valida con il
  `BlockRegistry`; `entries.py` (bozza, indirizzo, cestino) ed `entry_publishing.py` (pubblicazione e programmazione);
  sul sito `public_pages` risolve `/<elenco>/<slug>` e `public_render` prepara `listing` ed `entry` nel contesto.
- API dell'amministrazione: `GET/PATCH/DELETE /messages[/<id>]`, `GET /messages/summary` (`messages.view`,
  admin e owner), `GET /audit` con filtri controllati (`audit.view`, solo owner), `/users`, `/auth/password`,
  `/auth/totp/*`. L'eliminazione di un messaggio scrive nel registro solo l'id.
- In sviluppo: `tasks.py dev` (Flask, 5000) + `tasks.py admin-dev` (Vite, 127.0.0.1:5173/admin/, proxy verso Flask).
- `admin/scripts/check-dist.mjs` fa fallire la build con script o stili inline, `data:` o indirizzi esterni;
  `tests/security/test_admin_source.py` controlla il sorgente anche senza Node (D-98).

## Rendering pubblico
1. Risolvi `path` → pagina pubblicata (o redirect / 404 del tema).
2. Carica layout dichiarato in `theme.json`, blocchi per zona, widget per area, menu.
3. Render con `SandboxedEnvironment`, autoescape ON, `FileSystemLoader` solo su `themes/<attivo>/`.
4. Cache HTML per tema+lingua+path, in memoria in ogni processo; `site_state.cache_generation` nel database cresce a ogni modifica visibile (pubblica, programmata, ritira, cestino, cambio indirizzo, riordino; dalla Fase 6 widget, menu, impostazioni) e ogni processo, vedendo il numero nuovo, svuota la sua cache. Niente cache per anteprima, pagine con modulo contatti, 404 e invii di form (D-54).
5. Le pagine con programmazione scaduta si pubblicano al momento della richiesta se il cron è in ritardo (`ensure_due`, D-16).

## Sicurezza (difesa in profondità per il lock del template)
- Container: `themes/` montato `:ro`; l'utente del processo non ha permessi di scrittura.
- Codice: `services/theme.py` senza metodi di scrittura; nessuna route accetta path di file.
- Upload: allowlist verificata sui byte (jpg, png, webp, gif, pdf); SVG rifiutati; immagini re-encodate con Pillow senza metadati; nomi file rigenerati; storage fuori da `themes/` e da `app/`; solo `media_storage.py` scrive file (allowlist in `tests/security/test_golden_rule.py`).
- Input: JSON Schema + nh3; i dati dei blocchi non sono mai interpretati come template.
- Settings tema: solo chiavi dichiarate in `theme.json`, tipi validati (colore = regex hex, ecc.), nessun campo CSS/JS libero.
- CSP restrittiva sul sito e sull'admin; cookie `Secure`, `HttpOnly`, `SameSite=Lax`.
- Test automatici in `tests/security/test_template_lock.py`.

## Deploy
- `Dockerfile` multi-stage (build admin con Node → runtime Python slim).
- `docker-compose.yml`: app + Caddy; volumi `data/` (db), `media/`; `themes/` copiato nell'immagine (quindi cambia solo con nuovo build).
- Backup notturno DB + media (script `scripts/backup.sh`).
