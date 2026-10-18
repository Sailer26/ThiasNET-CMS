# Roadmap — ThiasNET CMS

Una fase alla volta. Una fase è chiusa solo quando tutti i criteri sono spuntati e `make test` + `make lint` sono verdi.

## Fase 0 — Fondamenta
- [x] Repo, `pyproject.toml`, `Makefile`, ruff/mypy, pre-commit, Docker dev
- [x] App factory Flask, config per ambiente, SQLAlchemy + Alembic, SQLite WAL
- [x] `services/theme.py`: carica e valida `theme.json` (JSON Schema); avvio fallisce se invalido
- [x] `tests/security/test_template_lock.py` attivo (anche se alcune parti sono ancora `skip` dove le route non esistono)
- [x] CI (GitHub Actions): test + lint

**Rimandati dalla review della Fase 0** (da chiudere nella fase indicata):
- ~~Fase 1: cookie `REMEMBER_*`, `__Host-session`, `PERMANENT_SESSION_LIFETIME`; mypy su `tests/` e `scripts/`~~ (fatto in Fase 1).
- Fase 3: `theme-check` verifica che esistano i template (`layouts/*.html`, `blocks/<tipo>.html`) e avvisa sulle varianti di blocchi mai ammessi in una zona; controllo del formato reale delle miniature (WebP/PNG/JPG); il tema `default` riceve `block_variants` reali; aggiungere l'`Environment` di `services/render.py` all'allowlist di `tests/security/test_golden_rule.py`.
- Fase 6: validazione server dei valori delle settings salvati dal pannello (url solo http(s)/relativo, colori nella palette).
- Fase 8: immagine base Docker per digest, `pip install --require-hashes` o lockfile, action e hook fissati a SHA.

## Fase 1 — Utenti e autenticazione
- [x] Modello `users`, ruoli owner/admin/editor, Argon2
- [x] Login/logout, sessione, CSRF, rate limit login, TOTP opzionale
- [x] Decoratore permessi + test per ogni ruolo
- [x] Comando `flask create-owner`
- [x] `audit_log` base

**Rimandati dalla review della Fase 1** (da chiudere nella fase indicata):
- Fase 2: `server_default` per le colonne NOT NULL con default (migrazione); rifiutare una nuova password uguale alla vecchia e una piccola lista di password comuni.
- Fase 5: valutare `SameSite=Strict` per il cookie di sessione del pannello; teardown esplicito della fixture `app` nei test.
- Fase 8: header CSP/HSTS in Caddy; verifica di `TRUSTED_PROXY_COUNT` nel deploy (D-34); retention o aggregazione di `audit_log` per i login falliti; limite globale per account contro attacchi distribuiti (oggi solo per email+IP, per IP e per il TOTP, D-24); limite di concorrenza su `/auth/login` in Caddy (costo Argon2).

## Fase 2 — Pagine e blocchi (backend)
- [x] Modelli pagine, blocchi, revisioni (+ bozze e reindirizzamenti, migrazione 0004)
- [x] Registry blocchi + JSON Schema per i 13 blocchi base (incluso `hero`, D-11)
- [x] Validazione zone/blocchi ammessi e varianti (`block_variants`) da `theme.json` (D-03)
- [x] `users.can_publish` per editor (D-15); job `flask publish-scheduled` (D-16)
- [x] Bozze autosave (`page_drafts`) separate dalla versione pubblicata (D-07)
- [x] Sanitizzazione rich text (nh3) + test XSS
- [x] API CRUD pagine/blocchi, riordino, bozza/pubblica/programma, ripristino revisione
- [x] Rimandi della Fase 1: `server_default` per users (migrazione 0003), password uguale all'attuale e password comuni rifiutate

**Rimandati dalla Fase 2** (da chiudere nella fase indicata):
- Fase 3: servire i 301 da `page_redirects` e ignorare quelli verso pagine non online; usare `publishing.ensure_due` al momento della richiesta (D-16); il sito mostra solo `status = published`.
- Fase 4: verificare che i `media_id` dei blocchi esistano (`registry.media_ids`) e bloccare l'eliminazione dei media in uso; alt obbligatorio prima di pubblicare (D-09).
- Fase 5: il pannello genera gli `uid` dei blocchi (D-39) e gestisce il 409 `version_conflict` mostrando chi ha salvato.

## Fase 3 — Rendering pubblico
- [x] Sandboxed Jinja, loader limitato al tema attivo, helper `img()` e `safe_html` (D-52, D-56)
- [x] Tema `default` completo (layout, partials, blocchi), accessibile e responsive, varianti reali (D-64)
- [x] Risoluzione path, 404 del tema, redirect, sitemap, robots, canonical (D-50, D-51, D-62, D-65)
- [x] Cache HTML + invalidazione (D-54)
- [x] Anteprima bozza per utenti loggati + endpoint anteprima live con `data-block-id` (D-02, D-55)
- [x] Banner consenso cookie, video/mappe "clicca per caricare", analytics solo dopo consenso (D-06, D-60, D-66)
- [x] Modulo contatti: invio SMTP, honeypot, rate limit, tempo minimo, `contact_messages` (D-05, D-61, D-67)
- [x] Rimandi delle Fasi 0–2: theme-check sui template e sulle miniature (D-63), `block_variants` reali, Environment del renderer in allowlist, 301 da `page_redirects`, `ensure_due` a richiesta

**Rimandati dalla Fase 3** (da chiudere nella fase indicata):
- Fase 4: `img()` e `media_url()` veri (oggi vuoti sul sito, segnaposto in anteprima), `og:image`, link dei file scaricabili.
- Fase 5: messaggi del modulo contatti nel pannello; il pannello usa l'anteprima live (`POST /_preview/<id>` con `target` sull'iframe, messaggi `cms:block-click` / `cms:highlight`); test automatici di `consent.js` e `preview.js`.
- Fase 6: menu configurati (oggi menu automatico, D-58), widget, impostazioni del sito e del tema dal pannello con `page_cache.mark_changed()`.
- Fase 7: hreflang e selettore lingua.
- Fase 8: CSP con l'host di Matomo e degli iframe, axe e Lighthouse automatici, dati strutturati, `python -m app.theme_check` nel build Docker, cron per `publish-scheduled`, `send-contact-messages` e `purge-contact-messages`; far rivedere i testi in romancio.

## Fase 4 — Media library
- [x] Upload con verifica del tipo sui byte, allowlist (JPG, PNG, WebP, GIF, PDF), 15 MB, 25 megapixel, SVG rifiutati, spazio per sito (D-70, D-71, D-78)
- [x] Re-encode, strip EXIF/ICC, varianti WebP da `image_sizes`, focal point, `flask media-variants` dopo un cambio del tema (D-72, D-73, D-80)
- [x] Cartelle, ricerca, alt obbligatorio per pubblicare, dedup sha256, blocco eliminazione se in uso, "Sostituisci file" con lo stesso indirizzo (D-76, D-77, D-79, D-82)
- [x] Sito: `img()` responsive, `media_url()`, `media_file()`, `og:image`, distribuzione `/media` con cache e sandbox (D-75, D-81)
- [x] Rimandi delle Fasi 2–3: `media_id` dei blocchi verificati in pubblicazione, test del kit `test_template_lock.py` sui media attivi

**Rimandati dalla Fase 4** (da chiudere nella fase indicata):
- Fase 5: media picker, caricamento multiplo, punto focale con un clic, avvisi alt e doppioni, elenco delle pagine che usano un media.
- Fase 6: impostazioni `media` (logo, favicon) e widget come fonti di "in uso" + `page_cache.mark_changed()`.
- Fase 7: alt per lingua; copertine delle collezioni come fonti di "in uso".
- Fase 8: Caddy che serve `/media` dal volume, backup di `MEDIA_ROOT`, pulizia dei file orfani, limite di upload per utente, antivirus per i PDF.

## Fase 5 — Pannello admin (React)
Divisa in quattro sotto-fasi con una PR ciascuna (D-86, `docs/PIANO-FASE-5.md`).

**5a — Telaio, accesso, pagine**
- [x] Progetto `admin/` (Vite + React + TS), servito da Flask su `/admin/` con CSP rigida, job CI su Linux e Windows (D-87 … D-89, D-96)
- [x] Accesso con secondo fattore, sessione scaduta senza perdere lo schermo, CSRF rinnovato da solo (D-90, D-91)
- [x] Albero delle pagine: crea (anche la homepage), su/giù, sposta, indirizzo, cestina, cestino e recupero, stati (D-95)
- [x] 409 con il nome di chi ha salvato (D-92), `GET /api/admin/site`, marchio ThiasNET (D-99)

**5b-1 — Editor della pagina** (D-102 … D-115)
- [x] Moduli generati dagli schemi con etichette italiane; testo formattato con TipTap limitato all'allowlist (D-106, D-108)
- [x] Zone e blocchi: aggiungi da riquadri con disegno, su/giù, sposta in, duplica, elimina con Annulla (D-109, D-115)
- [x] Varianti da miniature, titolo, tipo di pagina, motori di ricerca (D-03, D-110)
- [x] Salvataggio automatico con scritta in alto, annulla/ripristina, conflitti con scelta (D-104, D-105)
- [x] Anteprima live affiancata (Modifica/Anteprima sul tablet), clic sul blocco apre il modulo (D-02, D-107)
- [x] Pubblica con conferma, errori con "Vai al campo", Ritira, Scarta (D-113)
- [x] Rimandi: `uid` dal pannello (D-39), 409 con chi ha salvato, test di `preview.js` e `consent.js`

**5b-2 — Media nell'editor, trascinamento, aiuti, primo e2e** · **5c — Libreria e amministrazione** · **5d — Aiuto e prova sul campo** (criteri qui sotto)
- [ ] Shell Vite+TS, login, layout, gestione errori/sessione scaduta
- [ ] Albero pagine, editor pagina con zone e blocchi drag&drop (dnd-kit), TipTap
- [ ] Anteprima live affiancata (iframe), click sul blocco → apre il form (D-02)
- [ ] Scelta varianti blocco da miniature (D-03)
- [ ] Autosave + annulla/ripristina (D-07)
- [ ] Media picker, gestione utenti (admin/owner), audit log (owner), messaggi del modulo contatti
- [ ] Tour guidato al primo accesso, suggerimenti accanto ai campi, controllo prima di pubblicare, "Chiedi a Thias" (D-08, D-09)
- [ ] UI tutta in italiano, PC + tablet, azioni rapide da telefono (D-10)
- [ ] Test d'uso con un cliente vero (PREMORTEM #6)

**Rimandati dalla 5b-1:**
- 5b-2: scelta e caricamento dei media nei campi (oggi in sola lettura), `GET /media?ids=`, dnd-kit, aiuti per video e mappa, e2e Playwright; chiavi stabili per gli elementi degli elenchi (oggi per posizione).
- 5d: barra del testo formattato con un solo punto di tabulazione (roving tabindex); banner dei cookie nascosto nell'anteprima del pannello se il test d'uso lo chiede.

**Rimandati dalla 5a:**
- 5b: titolo, layout e SEO della pagina nell'editor (oggi il clic sul titolo apre un segnaposto); bozza risalvata dopo un nuovo accesso.
- 5c: `blob:` nella CSP del pannello per l'anteprima dei file da caricare.
- 5d: menu "⋯" per le azioni delle righe su tablet, se il test d'uso lo chiede (oggi le azioni vanno a capo sotto il titolo).
- Fase 6: azione rapida "banner avviso" da telefono (D-97). Fase 7: lingue nel pannello (D-94), azione "notizia".
- Fase 8: Docker con `npm ci && npm run build` (che include il controllo CSP), Caddy per `/admin/assets/`, build obbligatoria all'avvio in produzione, e2e completi, `npm audit` e action fissate a SHA, axe sul pannello.
- Fase 8 (dalla review di sicurezza della 5a): guardiani della regola d'oro e del pannello basati sull'albero del codice (oggi controllano i nomi: `getattr` con nomi calcolati o import rinominati non si vedono), `eslint-plugin-jsx-a11y` se l'audit axe lo chiede.

## Fase 6 — Widget, menu, impostazioni
- [ ] Widget per area con visibilità per pagina
- [ ] Menu per posizione, drag&drop, profondità massima
- [ ] Impostazioni sito + settings del tema generate da `theme.json` (form dinamico tipizzato) su `PUT /api/admin/settings/appearance` (D-14)

## Fase 7 — Collezioni e multilingua
- [ ] Collezioni da `theme.json` (news, eventi), listing paginato, dettaglio
- [ ] Traduzioni collegate, selettore lingua, hreflang

## Fase 8 — Produzione
- [ ] Dockerfile multi-stage, docker-compose con Caddy, `themes/` read-only
- [ ] Backup/restore DB+media, healthcheck, log strutturati
- [ ] CSP e security header, test e2e Playwright dei flussi principali
- [ ] Documentazione `docs/DEPLOY.md` e `docs/NUOVO-TEMA.md`
