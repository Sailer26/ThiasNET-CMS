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

**5b-2 — Media nell'editor, trascinamento, aiuti, primo e2e**
- [x] Scelta e caricamento di immagini e PDF nei campi, testo alternativo dall'editor, `GET /media?ids=` (D-111)
- [x] Trascinamento dei blocchi dentro una zona con maniglia, tocco prolungato e tastiera (D-109)
- [x] Aiuti "incolla il link" per video (YouTube, Vimeo) e mappa (OpenStreetMap, Google Maps) (D-112)
- [x] Primo e2e con Playwright: scrivi → anteprima → annulla → pubblica, Edge su Windows e Chromium in CI (D-114)

**5c-1 — Libreria e pagine** (D-116 … D-122, D-128, D-129)
- [x] Pagina Media: cartelle, ricerca e filtri, caricamento multiplo in coda con anteprima, spazio usato, dettaglio con punto focale, Sostituisci, Usato in, Elimina
- [x] Versioni nell'editor (Guarda, Ripristina nella bozza) e programmazione nell'ora svizzera
- [x] Chiavi stabili negli elenchi, Vimeo privato, link brevi spiegati; e2e per media e trascinamento

**5c-2 — Amministrazione** (D-123 … D-127, D-130, D-131)
- [x] Messaggi del modulo contatti: elenco con ricerca e "Da leggere", letto all'apertura, Rispondi, elimina con conferma, numero nel menu
- [x] Utenti: crea con password generata, modifica, disattiva, nuova password, azzera il codice a 6 cifre
- [x] Registro (owner): filtri per persona, tipo, giorni svizzeri e oggetto, etichette italiane, dettagli come testo
- [x] Profilo: password, codice a 6 cifre, esci da tutti i dispositivi; menu secondo i permessi; regola del 401; e2e

**5d-1 — Controlli e assistenza** (D-132, D-134 … D-137)
- [x] Controllo prima di pubblicare sul server (`GET /pages/<id>/checks`): bloccanti come la pubblicazione, avvisi (SEO, pagina vuota, link interni rotti) con "Pubblica comunque"
- [x] "Pubblica le modifiche" dal telefono con lo stesso controllo
- [x] "Chiedi a Thias": richieste salvate (migrazione `0009`), email a `SUPPORT_EMAIL`, limite per persona, nuovo invio e cancellazione dopo 12 mesi da CLI

**5d-2 — Guida e rifiniture** (D-133, D-138)
- [x] Tour di 5 passi al primo accesso (`POST /auth/me/tour`), menu Aiuto con "Chiedi a Thias" e "Rifai il tour"
- [x] Suggerimenti mancanti accanto ai campi (programmazione, utenti), barra del testo con un solo punto di tabulazione
- [x] Rimandi: registro con indicatore e controllo Dal/Al, numero dei messaggi azzerato all'uscita, "Apri nella libreria" dal selettore, avviso senza `SUPPORT_EMAIL`
- [x] e2e del tour e di "Pubblica comunque"; script del test d'uso in `docs/TEST-USO.md`

**Criteri della Fase 5**
- [x] Shell Vite+TS, login, layout, gestione errori/sessione scaduta
- [x] Albero pagine, editor pagina con zone e blocchi drag&drop (dnd-kit), TipTap
- [x] Anteprima live affiancata (iframe), click sul blocco → apre il form (D-02)
- [x] Scelta varianti blocco da miniature (D-03)
- [x] Autosave + annulla/ripristina (D-07)
- [x] Media picker, gestione utenti (admin/owner), audit log (owner), messaggi del modulo contatti
- [x] Tour guidato al primo accesso, suggerimenti accanto ai campi, controllo prima di pubblicare, "Chiedi a Thias" (D-08, D-09)
- [x] UI tutta in italiano, PC + tablet, azioni rapide da telefono (D-10)
- [ ] Test d'uso con un cliente vero (PREMORTEM #6) — lo fa Thias seguendo `docs/TEST-USO.md`; da lì si decidono menu "⋯", banner cookie nell'anteprima e QR (D-132)

**Rimandati dalla 5d-2:**
- Fase 8: limite di richieste anche su `POST /auth/me/tour` (scrive una volta sola: nessun danno); aggiornare l'utente della sessione dopo il tour (oggi si legge solo all'avvio del pannello).

**Rimandati dalla 5d-1:**
- Fase 8: invio delle email di assistenza fuori dalla richiesta, se il server di posta è lento (oggi come i messaggi del modulo contatti, con limite di 5 all'ora per persona); limite di richieste anche su `/checks`.

**Rimandati dalla 5c-2:**
- Fase 8: limite di richieste per utente su tutta `/api/admin` (oggi solo accesso e codice a 6 cifre); pagine nell'elenco utenti oltre 100.

**Rimandati dalla 5b-1:**
- 5c: chiavi stabili per gli elementi degli elenchi (oggi per posizione); link brevi (maps.app.goo.gl) e video Vimeo privati negli aiuti; e2e anche per media e trascinamento.
- Dopo il test d'uso: banner dei cookie nascosto nell'anteprima del pannello, se serve.

**Rimandati dalla 5a:**
- 5b: titolo, layout e SEO della pagina nell'editor (oggi il clic sul titolo apre un segnaposto); bozza risalvata dopo un nuovo accesso.
- 5c: `blob:` nella CSP del pannello per l'anteprima dei file da caricare.
- Dopo il test d'uso: menu "⋯" per le azioni delle righe su tablet, se serve (oggi le azioni vanno a capo sotto il titolo).
- ~~Fase 6: azione rapida "banner avviso" da telefono (D-97)~~ fatta nella 6c. Fase 7: lingue nel pannello (D-94), azione "notizia".
- Fase 8: Docker con `npm ci && npm run build` (che include il controllo CSP), Caddy per `/admin/assets/`, build obbligatoria all'avvio in produzione, e2e completi, `npm audit` e action fissate a SHA, axe sul pannello.
- Fase 8 (dalla review di sicurezza della 5a): guardiani della regola d'oro e del pannello basati sull'albero del codice (oggi controllano i nomi: `getattr` con nomi calcolati o import rinominati non si vedono), `eslint-plugin-jsx-a11y` se l'audit axe lo chiede.

## Fase 6 — Widget, menu, impostazioni
**6a — Impostazioni** (D-139, D-143, D-144)
- [x] Tabelle `settings` ed `entity_revisions` (migrazione `0010`), `GET /settings`, `PUT /settings/site` e `/settings/appearance` con versione, registro, versioni e cache
- [x] Validazione tipizzata (testo, email, url https per i social, colori della palette, scelte, sì/no, logo con alt); chiavi sconosciute rifiutate
- [x] Logo e stile della testata nel tema; il logo conta in "Usato in"; avviso al vecchio destinatario dei messaggi
- [x] Schermata Impostazioni nel pannello ("Dati del sito", "Aspetto"); e2e; test della regola d'oro senza più skip

**6b — Menu** (D-140, D-141, D-145)
- [x] Tabella `menus` (migrazione `0011`), `GET /menus`, `PUT` e `DELETE /menus/<posizione>` per chi può pubblicare, con versione, registro, versioni e cache
- [x] Menu principale automatico finché non si salva, "Torna automatico"; pagine risolte al render, sottovoci e menu del piè di pagina nel tema
- [x] Schermata Menu nel pannello: trascinamento tra sorelle, su/giù/rientra/esci, focus e annunci accessibili; e2e

**6c — Widget** (D-140, D-142, D-146)
- [x] Tabella `widget_areas` (migrazione `0012`), `GET /widgets`, `GET` e `PUT /widgets/<area>` per chi può pubblicare, con versione, registro, versioni e cache
- [x] Sette widget con schema e template nel tema (banner, contatti in riga, orari, contatti, social, testo, invito all'azione); visibilità per pagina; banner con "fino al"
- [x] Schermata Widget nel pannello e "Banner avviso" dal telefono (D-97); e2e; la sessione completa della regola d'oro salva anche i widget

**Criteri della Fase 6**
- [x] Widget per area con visibilità per pagina (6c)
- [x] Menu per posizione, drag&drop, profondità massima (6b)
- [x] Impostazioni sito + settings del tema generate da `theme.json` (form dinamico tipizzato) su `PUT /api/admin/settings/appearance` (D-14)

**Rimandati dalla 6c:**
- Fase 7: widget "ultime notizie" con le collezioni (schema e tipo già pronti, spento); azione rapida "notizia" dal telefono.
- Dopo il test d'uso: trascinamento dei widget (oggi su/giù), anteprima del widget nella finestra di modifica.
- Fase 8: scheletro comune per le liste salvate con versione (`menus.py` e `widgets.py` si somigliano molto: `_write`, `_conflict`, commit).

**Rimandati dalla 6b:**
- Dopo il test d'uso: "aria-current" diverso per la voce genitore della pagina aperta; pulsante per aprire i sottomenu sui tablet se le sottovoci sempre aperte disturbano.

**Rimandati dalla 6a:**
- Fase 8: limite di dimensione del corpo per le API JSON del pannello (oggi vale quello dei caricamenti); limite di richieste sulle scritture.

## Fase 7 — Collezioni e multilingua
- [ ] Collezioni da `theme.json` (news, eventi), listing paginato, dettaglio
- [ ] Traduzioni collegate, selettore lingua, hreflang

## Fase 8 — Produzione
- [ ] Dockerfile multi-stage, docker-compose con Caddy, `themes/` read-only
- [ ] Backup/restore DB+media, healthcheck, log strutturati
- [ ] CSP e security header, test e2e Playwright dei flussi principali
- [ ] Documentazione `docs/DEPLOY.md` e `docs/NUOVO-TEMA.md`
