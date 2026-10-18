# Passaggio di consegne — ThiasNET CMS (per una nuova sessione / nuovo account Claude)

Aggiornato: 2026-10-18. Leggi questo file **dopo** `CLAUDE.md` e prima di qualsiasi altra cosa.

## 1. Dove siamo
- Repository: https://github.com/Sailer26/ThiasNET-CMS (branch di default `main`)
- Cartella locale: `C:\Users\thias\progetti\ThiasNET CMS` (Windows 11, Python 3.12, Node 24, Git Bash)
- Identità git del repo: `Sailer26 <thias.nietli@gmail.com>` (impostata per-repo, non globale)
- **Fase 0 — Fondamenta:** chiusa e unita in `main`.
- **Fase 1 — Utenti e autenticazione:** chiusa e unita in `main` (PR #1, commit `e2ae055`). 235 test verdi, copertura 96.6 %, CI verde su Linux e Windows.
- **Fase 2 — Pagine e blocchi (backend):** completata sul branch `phase-2-pages` (600 test verdi, copertura 96 %, review ECC fatta, problemi alti e medi corretti). In attesa della PR verso `main`. Prossima: **Fase 3 — Rendering pubblico** (rimandi in ROADMAP).
- Le decisioni di prodotto sono in `docs/DECISIONI.md` (D-01 … D-49). Prevalgono sugli altri documenti.

## 2. Preparare l'ambiente (se la `.venv` non c'è)
```bash
cd "C:/Users/thias/progetti/ThiasNET CMS"
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/pre-commit install
```
Comandi (non c'è `make` su questo PC, D-17):
```bash
.venv/Scripts/python scripts/tasks.py test         # pytest + coverage (soglia 80 %)
.venv/Scripts/python scripts/tasks.py lint         # ruff check + ruff format --check + mypy
.venv/Scripts/python scripts/tasks.py theme-check  # valida i temi senza avviare l'app
```
L'app non parte senza `APP_ENV` (D-20); `tasks.py` usa `development` di default.

## 3. Come si lavora (obbligatorio, scelto da Thias)
- **Usare sempre ECC** (plugin `ecc@ecc`): piano con `ecc:planner`, TDD (test prima, poi codice), review finale in parallelo con `ecc:code-reviewer`, `ecc:python-reviewer` e l'agent di progetto `security-reviewer` (che esegue anche i controlli di `/check-template-lock`). Correggere tutti i problemi CRITICI/ALTI prima di chiudere una fase.
- Una fase alla volta (`docs/ROADMAP.md`), branch dedicato `phase-N-<nome>`, commit in italiano `tipo(ambito): descrizione`.
- Alla fine della fase: spuntare i criteri in ROADMAP, aggiungere le nuove decisioni in DECISIONI, push del branch. **Non c'è la CLI `gh`:** Thias apre la PR dal link `https://github.com/Sailer26/ThiasNET-CMS/compare/main...<branch>`.
- Thias non è uno sviluppatore di dettaglio: domande di prodotto in linguaggio semplice, poche e solo se bloccanti.
- Priorità di prodotto: (1) facilità d'uso per clienti non tecnici, (2) ogni sito con grafica unica sugli stessi blocchi (D-04).

## 4. Trappole note su questo progetto
- **GateGuard (ECC)** blocca il primo Write/Edit di ogni file e il primo Bash della sessione: va ripetuta la stessa operazione dopo aver dichiarato i fatti richiesti (chi usa il file, dati toccati, istruzione dell'utente). Se Thias vuole evitarlo può impostare `GATEGUARD_EXEMPT_GLOBS` (è una sua impostazione: non cambiarla da soli).
- **Regola d'oro:** `tests/security/test_golden_rule.py` vieta in `app/` qualsiasi chiamata di nome `copy`, `remove`, `move`, `rename`, `save`, `write_text`, `mkdir`… (allowlist: solo `database.py` → `mkdir`) e la costruzione di template (`Template`, `Environment`, `from_string`…). Quindi: niente `dict.copy()` o `list.remove()`; usare comprehension/`copy.deepcopy`; nominare le funzioni `move_page`, `trash_page`, `store_draft`. In Fase 3 l'`Environment` del renderer va aggiunto all'allowlist.
- **pre-commit** fa girare mypy su tutto il progetto: commit parziali con moduli che dipendono da file non ancora aggiunti falliscono. Fare commit coerenti (o un commit unico per l'area).
- `mixed-line-ending` di pre-commit corregge file con CRLF e fa fallire il commit: rifare `git add` e ricommittare.
- Test: la fixture `app` crea il DB in memoria con `create_all` e **non tiene il contesto attivo** durante le richieste (altrimenti `g`/utente loggato verrebbero condivisi). Usare `make_user(app, …)`, `api_client(app)`, `login(...)`, `adopt_csrf(...)` da `tests/helpers.py` e la fixture `login_as(role)`.
- Le migrazioni sono scritte a mano; `tests/unit/test_models.py::test_migrations_match_models` verifica la parità con i modelli. Gli indici parziali non sono confrontati da `compare_metadata`: serve un test dedicato.
- Ogni route `/api/admin/*` deve avere `@require_permission(...)` o `@public` (meta-test `tests/api/test_route_permissions.py`).
- Script Python che scrivono file su Windows: usare `newline="\n"` (altrimenti CRLF e pre-commit fallisce). Nei testi passati agli strumenti di scrittura gli escape Unicode possono diventare caratteri invisibili veri: nei sorgenti usare `chr(0x...)`.
- `.gitignore` esclude solo `/data/` della radice (database): `app/data/` (password comuni) è nel repository.
- I test del kit in `tests/security/test_template_lock.py` su media (Fase 4) e settings (Fase 6) sono saltati con skip mirati: `test_golden_rule.py` fallisce se la route nasce e lo skip resta. Toglierli nella fase giusta.

## 5. Fase 2 — domande per Thias (risposta: tutte le proposte, registrate in D-40, D-43, D-45)
1. **Pagina eliminata:** cestino recuperabile, per ora non svuotabile dal pannello; un editor senza permesso di pubblicazione non può cestinare una pagina online. *(Proposta)* — alternativa: l'admin può anche eliminare definitivamente.
2. **Versioni precedenti per pagina:** ultime 50 *(proposta)* — alternative: 20, oppure tutte.
3. **Cambio indirizzo di una pagina online:** reindirizzamento 301 automatico dal vecchio al nuovo, attivo in Fase 3 *(proposta)* — alternativa: lo gestisce il cliente a mano.
4. **Livelli di sottopagine:** massimo 4; homepage a sé, pagine principali al primo livello *(proposta)* — alternative: 3, oppure nessun limite.

Una volta avute le risposte: registrarle come decisioni D-38 … D-49 (vedi piano) e partire con i test.

## 6. Piano della Fase 2 (prodotto con `ecc:planner`, da confermare con le risposte sopra)

### Decisioni proposte
- **D-38 Contenuto:** pubblicato in `pages` (titolo, layout, seo) + `blocks`; copia di lavoro come documento JSON unico in `page_drafts` (`title, layout, seo, zones→[blocchi]`). Pubblicare = rivalidare la bozza, sostituire i `blocks` in una transazione, scrivere una revisione, cancellare la bozza. L'autosave non tocca mai il pubblicato (D-07); l'anteprima live (Fase 3) usa lo stesso documento; `blocks` permette di sapere quali media sono in uso (Fase 4).
- **D-39** Ogni blocco ha un `uid` stabile (32 hex) generato dal pannello e validato dal server (serve a `data-block-id`, annulla/ripristina, riordino).
- **D-40 Revisioni:** create a pubblica, programma, ritira; prima di un ripristino si salva la bozza corrente (kind `draft`); l'autosave non crea revisioni; ultime 50 per pagina (la revisione programmata in attesa non si pota).
- **D-41 Audit:** una riga per ogni azione esplicita (create, update_meta, move, publish, schedule, unschedule, unpublish, trash, restore, revision_restore, draft_discard); per l'autosave solo `page.draft_started` alla nascita della bozza; diff solo dei campi cambiati.
- **D-42** Ripristinare una revisione la copia in bozza, non pubblica mai.
- **D-43 Cestino:** `deleted_at`; si recupera come bozza non pubblicata; nessuno lo svuota in Fase 2; non si cestina una pagina con sottopagine (409) né la homepage (409); cestinare una pagina pubblicata/programmata richiede `content.publish`.
- **D-44 Blocco ottimistico:** `page_drafts.version` e `pages.version` interi; ogni scrittura manda la `version` conosciuta; se diversa → 409 `version_conflict` (con versione, autore, data correnti). UPDATE condizionato `WHERE version=:v`.
- **D-45 Slug e percorsi:** slug `^[a-z0-9]+(-[a-z0-9]+)*$` ≤ 80, generato dal titolo (NFKD, ä→ae…); `path` calcolato dall'albero e salvato; unico per (locale, path) tra le pagine non cestinate; profondità massima 4; cicli rifiutati; primi segmenti riservati `api, admin, _preview, static, media, assets, sitemap.xml, robots.txt, it, de, rm, en`; homepage una per lingua (slug "", path "/", niente genitore né figli); cambio slug/genitore ricalcola i discendenti nella stessa transazione e, se la pagina è online, richiede `content.publish`.
- **D-46 Validazione a due livelli:** "bozza" (tipi, lunghezze, `additionalProperties`, sanitizzazione, regole del tema, ma `required` ignorato) e "pubblica" (tutto).
- **D-47 Programmazione:** `publish_at` ISO 8601 con fuso obbligatorio, salvato in UTC, futuro e ≤ 1 anno; congela la bozza in una revisione `kind=scheduled` (al massimo una in attesa); `publish_due(now)` rivalida contro il tema attuale e, se non valida, scrive `page.schedule_failed`; `status=scheduled` solo per pagine mai pubblicate.
- **D-48 Permessi:** nessun nuovo valore. `content.edit`: crea, modifica, bozza, riordino, ripristino revisioni, cestino di pagine non pubblicate. `content.publish`: pubblica, programma, annulla programmazione, ritira, cestino di pagine online, slug/spostamento di pagine online. Controllo nel service (403).
- **D-49** nh3 aggiunge `rel="noopener noreferrer"` a tutti i link (`link_rel`), anche interni.

### Modello dati
- **pages:** id, parent_id (FK pages, RESTRICT), locale String(5), translation_group String(36) (uuid), slug String(80), path String(255), title String(200), layout String(64), status (CHECK draft|published|scheduled), publish_at, published_at, seo_json JSON, sort (server_default 0), version (server_default 1), created_by/updated_by (FK users SET NULL), created_at, updated_at, deleted_at, deleted_by. Indici: unique parziale (locale, path) WHERE deleted_at IS NULL (`sqlite_where` + `postgresql_where`), ix parent_id, ix (status, publish_at), ix translation_group.
- **blocks:** id, page_id (FK CASCADE), uid String(32), zone String(64), type String(32) (CHECK su BLOCK_TYPES), variant String(64) nullable, data_json JSON, sort. uq(page_id, uid), ix(page_id, zone, sort).
- **page_revisions:** id, page_id (FK CASCADE), kind (CHECK published|scheduled|unpublished|draft), snapshot_json JSON, author_id (FK SET NULL), created_at. ix(page_id, created_at); unique parziale (page_id) WHERE kind='scheduled'.
- **page_drafts:** page_id (PK+FK CASCADE), data_json JSON, version (server_default 1), author_id (FK SET NULL), created_at, updated_at.
- Forma di snapshot/bozza: `{title, layout, seo:{title≤70, description≤160, og_image_media_id, noindex}, zones:{zone:[{uid,type,variant,data}]}}`; massimo 200 blocchi e 512 KB.
- Migrazioni: `0003_server_defaults` (users.active true, can_publish false, session_version 1; parità con `compare_server_default=True`) e `0004_pages` (4 tabelle, con downgrade).

### Registry dei blocchi
- Schemi in `app/blocks/<tipo>.schema.json` (package-data), registry immutabile in `app/services/blocks.py` che carica all'avvio, fa `check_schema` e verifica che i tipi coincidano con `core_types.BLOCK_TYPES` (altrimenti l'avvio fallisce).
- Annotazioni: `x-richtext` (HTML da sanitizzare), `x-media` (intero ≥ 1), formato `safe-url` (http(s), mailto, tel, relativo con "/" ma non "//", ≤ 2048, senza spazi/controlli) con FormatChecker dedicato.
- Stringhe non rich: NFC, niente caratteri di controllo (tranne \n), trim; mai trattate come HTML.
- `media_ids(block)` per la Fase 4 (l'esistenza dei media si verifica in Fase 4).
- Meta-test sugli schemi: ogni oggetto `additionalProperties:false`, ogni stringa con `maxLength`/enum/pattern, ogni array con `maxItems`, nessun campo html/raw/embed/script/style.
- I 13 schemi (rich = x-richtext, req = obbligatorio per pubblicare):
  - hero: title≤120 req, subtitle≤300, media_id req, cta_label≤40 + cta_url safe-url (entrambi o nessuno)
  - heading: text≤200 req, level 2|3|4 (default 2), anchor slug≤60
  - text: **body rich≤20000** req
  - image: media_id req, caption≤300, link safe-url (alt sul media)
  - gallery: items 1..48 di {media_id req, caption≤200}
  - text_image: title≤200, **body rich≤10000**, media_id req, cta_label≤40 + cta_url
  - cta: title≤120 req, text≤300, button_label≤40 req, url safe-url req
  - quote: text≤600 req, author≤120, role≤120
  - video: provider youtube|vimeo, video_id con pattern (YouTube `^[A-Za-z0-9_-]{11}$`, Vimeo `^\d{1,12}$`), title≤200 req; niente URL libero né iframe
  - divider: `{}`
  - map: lat −90..90 e lng −180..180 req, zoom 1..19, label≤120, address≤300; niente iframe
  - files: title≤120, items 1..50 di {media_id req, label≤120}
  - contacts: title≤120, intro≤500, address≤300, phone≤30 con pattern, email ≤254, show_form bool (il destinatario sta nelle impostazioni, D-05)
- Regole del tema `validate_content(theme, doc, mode)`: layout esiste; zona esiste nel layout; tipo ammesso nella zona; `max` per zona; variante assente → default del tema, non dichiarata o su blocco senza varianti → 422; locale ∈ `theme.locales`; errori con percorso (zona/indice/campo).

### API (`/api/admin`, envelope ok/fail; `fail()` riceve un `details` opzionale con i percorsi degli errori)
| Metodo e path | Permesso | Body | Risposte |
|---|---|---|---|
| GET /pages?locale&parent_id&status&q&page&limit | edit | – | 200 + meta |
| GET /pages/tree?locale | edit | – | 200 (tetto 2000) |
| POST /pages | edit | title, layout, locale?, parent_id?, slug? | 201 (con bozza iniziale) · 409 slug_taken · 422 |
| GET /pages/<id> | edit | – | 200 |
| PATCH /pages/<id> | edit (+publish se online) | version, slug?, parent_id? | 200 · 409 · 422 |
| POST /pages/reorder | edit | parent_id, locale, ids[] | 200 · 422 |
| DELETE /pages/<id> | edit (+publish se online) | – | 200 (cestino) · 409 |
| GET /pages/trash · POST /pages/<id>/restore | edit | – | 200 · 409 path_taken |
| GET /pages/<id>/draft | edit | – | 200 (senza bozza: pubblicato con version 0) |
| PUT /pages/<id>/draft | edit | version, title, layout, seo, zones | 200 {version} · 409 · 413 · 422 |
| DELETE /pages/<id>/draft | edit | version | 200 |
| POST /pages/<id>/draft/blocks | edit | version, zone, type, variant?, data, position? | 201 |
| PATCH·DELETE /pages/<id>/draft/blocks/<uid> | edit | version, variant?/data? | 200 · 404 |
| POST /pages/<id>/draft/blocks/reorder | edit | version, zones:{zone:[uid]} | 200 · 422 |
| POST /pages/<id>/publish | publish | draft_version | 200 · 409 · 422 |
| POST · DELETE /pages/<id>/schedule | publish | draft_version, publish_at | 200 · 422 |
| POST /pages/<id>/unpublish | publish | version | 200 |
| GET /pages/<id>/revisions · GET …/revisions/<rid> | edit | – | 200 · 404 |
| POST /pages/<id>/revisions/<rid>/restore | edit | draft_version | 200 (va in bozza) |
| GET /blocks | edit | – | schemi, layout, zone, blocchi ammessi, varianti |

CLI `flask publish-scheduled` (cron ogni minuto): idempotente, UPDATE condizionato sulla revisione in attesa con controllo del rowcount; `publishing.ensure_due(page)` pronto per il controllo a richiesta in Fase 3.

### File (in ordine)
1. `pyproject.toml`: `nh3` (verificare l'ultima 0.3.x con `pip index versions nh3`), package-data `blocks/*.json`, `data/*.txt`.
2. `app/models/user.py` (server_default) + `migrations/versions/0003_server_defaults.py`.
3. `app/data/common_passwords.txt` (~200 voci ≥ 12 caratteri, anche it/de) + `app/services/passwords.py` (`check_not_common`, confronto NFKC+casefold); `services/auth.change_password` e `services/users.update_user`: 422 se la nuova password è uguale all'attuale.
4. `app/blocks/*.schema.json` (13), `app/services/sanitize.py`, `app/services/blocks.py`.
5. `app/models/page.py` (Page, Block, PageRevision, PageDraft), `app/models/__init__.py`, `migrations/versions/0004_pages.py`.
6. Servizi (ognuno < 400 righe): `slugs.py`, `pages.py` (CRUD, albero, cestino, path), `drafts.py` (documento, blocchi, locking), `publishing.py` (publish, schedule, unpublish, publish_due), `revisions.py` (list, restore, prune).
7. `app/api/__init__.py` (details), `app/api/admin/pages.py`, `page_drafts.py`, `blocks.py`, registrazione in `app/api/admin/__init__.py`.
8. `app/cli_pages.py` + registrazione in `app/cli.py`.
9. Docs: DECISIONI (D-38..D-49), ARCHITETTURA, ROADMAP (spunte e rimandi), IDEE (svuota cestino, "salva versione" manuale).

### Test da scrivere per primi
- Modelli/migrazioni: parità con `compare_server_default`; CHECK su status, type, kind; unique (locale, path) ignora i cestinati; cascade di blocks e draft.
- Registry: 13 schemi = BLOCK_TYPES; meta-test sugli schemi; per ogni tipo un caso valido e gli invalidi (campo extra, troppo lungo, media_id stringa o 0, safe-url `javascript:`/`//evil`/`data:`, video_id errato, lat fuori intervallo); bozza vs pubblica sui `required`; pulizia delle stringhe plain (`<script>` resta letterale).
- Regole del tema (con `make_theme` + `create_app(overrides=THEMES_DIR/ACTIVE_THEME)`): layout/zona/locale sconosciuti, hero in main, 2 hero in home.hero, 5 blocchi in page.sidebar, variante assente → default, variante non dichiarata, variante su blocco senza varianti, cambio di layout con zone sparite, tema cambiato dopo l'autosave → publish 422.
- XSS (`tests/security/test_richtext_xss.py`, sul sanitizer e sull'API PUT draft): `<script>`, `<img onerror>`, `<svg onload>`, `<math><mi xlink:href>`, `<a href="javascript:">` in tutte le varianti (JaVaScRiPt, `java\tscript:`, `&#106;avascript:`, spazio iniziale), `data:text/html;base64`, `vbscript:`, `//evil.com`, `<iframe>`, `<object>`, `<embed>`, `<style>@import`, `<link>`, `<base>`, `<meta http-equiv=refresh>`, `<form><input>`, attributi `style`/`onclick`/`target`, mXSS `<noscript><p title="</noscript><img src=x onerror=…>">`, commenti, byte nullo, tag non chiusi, h1/h5 → solo testo. Positivi: allowlist intatta, link http/mailto/tel/relativi con rel, sanitizzazione idempotente, `{{ 7*7 }}` letterale.
- Slug/albero: slugify con accenti e umlaut; riservati e codici lingua; profondità > 4; ciclo; ricalcolo discendenti; homepage unica, senza figli, non cestinabile; cestino con figli 409; ripristino con path occupato 409.
- Bozze/locking: l'autosave non cambia `blocks` né status; version vecchia 409; uid duplicato/sconosciuto; riordino con insieme diverso 422; 413 oltre 512 KB; una sola riga `draft_started`.
- Pubblicazione: editor senza/con can_publish (403/200); publish sostituisce i blocks, scrive revisione e audit, cancella la bozza; schedule con data passata o senza fuso 422; `publish_due` solo pagine scadute, idempotente, `schedule_failed` con tema invalido; CLI con `test_cli_runner`; unpublish; cestino di pagina online senza publish 403.
- Revisioni: ripristino in bozza (salvando prima la bozza esistente); potatura a 50; la programmata non si pota.
- Permessi: `tests/unit/test_permissions.py` con matrice completa; `test_route_permissions` verde senza nuove route pubbliche.
- Password: uguale all'attuale 422; password comune (anche maiuscole/forme Unicode) 422.

### Commit proposti
1. `chore(deps): aggiungi nh3 per la sanitizzazione del rich text`
2. `fix(db): server_default per le colonne NOT NULL di users (migrazione 0003)`
3. `feat(auth): rifiuta nuova password uguale all'attuale e password comuni`
4. `feat(blocchi): registry e schemi JSON dei 13 blocchi base`
5. `feat(sicurezza): sanitizzazione rich text con nh3 e test XSS`
6. `feat(pagine): modelli pages, blocks, page_revisions, page_drafts (migrazione 0004)`
7. `feat(pagine): albero, slug, percorsi riservati e cestino`
8. `feat(pagine): bozze autosave con blocco ottimistico e operazioni sui blocchi`
9. `feat(pagine): pubblica, programma, ritira, revisioni e comando publish-scheduled`
10. `feat(api): route /api/admin/pages e /api/admin/blocks`
11. `docs(decisioni): D-38..D-49 e chiusura Fase 2 in ROADMAP`

(Se pre-commit rende impossibili commit separati per le dipendenze tra moduli, accorparli per area.)
