# Piano della Fase 5 — Pannello admin (React)

Prodotto con `ecc:planner` il 2026-10-18 sul branch `phase-5-admin` (partito da `phase-4-media`).
Le decisioni stanno in `docs/DECISIONI.md` (D-86 … D-99), che prevale su questo documento.
La fase si divide in **quattro sotto-fasi con una PR ciascuna** (D-86): qui la **5a** è descritta
nel dettaglio, 5b–5d a grandi linee (ognuna avrà il suo piano all'inizio).

## Risposte di Thias (tutte le proposte)
1. **Aspetto:** colori e logo **ThiasNET**, uguale per tutti i clienti, con il nome del sito in alto. → D-99
2. **Elenco delle pagine:** **albero** con sottopagine rientrate e pulsanti "Su", "Giù", "Sposta in…". → D-95
3. **All'ingresso:** **subito l'elenco delle pagine** (benvenuto eventualmente in 5d). → D-95
4. **Nuova pagina:** **solo il titolo**; nasce col primo layout del tema, il tipo si cambia dopo. → D-95

## Punti trovati prima di iniziare
1. `scripts/tasks.py lint` lancia `npm`: su Windows serve `npm.cmd` (`shutil.which`), e la CI Python non ha Node → comandi `admin-*` separati, `lint` solo Python (D-96).
2. `app/public/routes.py` riserva `admin` (404): le route del pannello devono vincere su `/<path:path>` → test espliciti.
3. `app/public/responses.py` mette la CSP del sito con `setdefault` fuori da `/api/`: il pannello imposta la sua CSP nella view.
4. `tests/security/test_golden_rule.py::EXPECTED_PUBLIC_ROUTES` va aggiornato con le route `/admin…` (sola lettura).
5. `render_template` è vietato: `index.html` si serve come file statico, mai con Jinja.
6. Il 409 `version_conflict` ha solo `updated_by` (id): un editor non può leggere gli utenti (D-33) → `updated_by_name` dal server (D-92). Gli utenti non hanno un nome, solo l'email (D-93).
7. Il pannello non ha da dove leggere nome e indirizzo del sito → `GET /api/admin/site`.
8. `CSRFProtect` controlla prima della view: a sessione scaduta un POST riceve 403 `csrf` prima del 401 → token nuovo e un solo nuovo tentativo.
9. `SESSION_REFRESH_EACH_REQUEST = True`: un timer verso l'API terrebbe viva la sessione e annullerebbe D-27 → niente timer (D-90).
10. L'anteprima vuole stessa origine: il proxy di Vite passa `/api`, `/_preview`, `/static`, `/assets`, `/_vars.css`, `/media`.
11. `POST /pages/reorder` vuole l'elenco completo delle sorelle; `reorder_mismatch` → ricaricare l'albero.
12. Errori di cestino e spostamento (`home_protected`, `has_children`, `cycle`, `too_deep`, `home_has_no_children`, `home_is_fixed`, `path_taken`/`slug_taken`) hanno già messaggi in italiano: il pannello li mostra.
13. Sito senza homepage: l'albero propone "Crea la homepage" (`POST /pages` con `slug: ""`).
14. Il tema dichiara 4 lingue ma le traduzioni arrivano in Fase 7 → D-94.
15. D-10: "banner avviso" (widget, Fase 6) e "notizia" (collezioni, Fase 7) non esistono ancora → D-97.
16. Per dopo: `support_requests` non ha modello (5d), `tour_completed_at` non ha endpoint (5d), nessuna API per i messaggi del modulo contatti (5c).
17. CSP: Vite deve avere `assetsInlineLimit: 0` e `modulePreload.polyfill: false`; TipTap `injectCSS: false` (5b).

## Le quattro sotto-fasi
| Sotto-fase | Contenuto |
|---|---|
| **5a — Telaio, accesso, pagine** (ora) | progetto `admin/` (Vite+React+TS), Flask che serve `/admin/` con CSP, proxy di sviluppo, CI Node Linux+Windows, accesso (anche TOTP), sessione scaduta, CSRF, struttura del pannello in italiano col marchio ThiasNET, albero delle pagine (crea, su/giù, sposta, indirizzo, cestina, cestino e recupero, stati), 409 con il nome, `GET /api/admin/site`, `SameSite=Strict` |
| **5b — Editor della pagina** | form generati dagli schemi dei 13 blocchi, TipTap con le sole voci di D-49, media picker di base, zone, dnd-kit, `uid` dal pannello (D-39), varianti da miniature, autosave + annulla/ripristina, anteprima live affiancata, titolo/layout/SEO, pubblica/ritira, test di `preview.js` e `consent.js`, primo e2e Playwright |
| **5c — Libreria e amministrazione** | pagina Media completa, revisioni e programmazione, utenti, registro attività, profilo (password, TOTP), messaggi del modulo contatti (API nuova) |
| **5d — Aiuto e prova sul campo** | tour (D-08), suggerimenti, controllo prima di pubblicare (D-09), "Chiedi a Thias", "Pubblica" da telefono (D-97), eventuale benvenuto, **test d'uso con un cliente vero** (PREMORTEM #6) |

## 5a — Architettura

### Flask serve il pannello (D-87, D-88)
- Blueprint `app/panel.py` (route sottili); regole sui percorsi in `app/services/panel_assets.py`.
- `GET /admin/` e `GET /admin/<path:subpath>` → `index.html` della build; `GET /admin/assets/<path:filename>` → solo file esistenti con estensione `.js`, `.css`, `.woff2`, `.png`, altrimenti 404. `/admin` → 308. Il logo ThiasNET è un componente React (SVG nel codice), non un file.
- `index.html`: `no-cache`, CSP del pannello, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `nosniff`, `Cross-Origin-Opener-Policy: same-origin`. Asset: un anno, `immutable`.
- CSP: `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; frame-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'; object-src 'none'`.
- `ADMIN_DIST_DIR` (default `admin/dist`): mai dentro `themes/` o `app/`; in produzione obbligatoria con `index.html`; in sviluppo senza build → 503 con testo fisso "Pannello non ancora compilato: esegui `python scripts/tasks.py admin-build`".

### Sviluppo
- `tasks.py dev` → Flask su 5000; `tasks.py admin-dev` → Vite su `127.0.0.1:5173/admin/` con proxy (punto 10).
- `vite.config.ts`: `base: '/admin/'`, `assetsInlineLimit: 0`, `modulePreload: { polyfill: false }`, niente sourcemap in produzione.

### Sessione, CSRF, errori (D-90, D-92)
- Avvio: `GET /auth/csrf` poi `GET /auth/me` (401 → accesso).
- Token CSRF solo in memoria, header `X-CSRFToken` sulle scritture, sostituito da quello restituito da login/TOTP/logout/password.
- `api/client.ts`: busta `{success, data, error, meta}` → `ApiError`; 403 `csrf` → un nuovo tentativo; 401 → finestra "Per sicurezza devi accedere di nuovo" che conserva lo schermo; 429 con i minuti; rete assente; 500.
- Un solo controllo `GET /auth/me` quando la finestra torna visibile dopo più di 15 minuti.
- 409: "Nel frattempo **{nome}** ha modificato questa pagina. Ho ricaricato l'elenco: controlla e riprova." Mai nuovi tentativi automatici.

### Albero delle pagine (D-95)
- `/admin/pagine` da `GET /pages/tree?locale=<prima lingua>`: homepage in cima, sottopagine rientrate (4 livelli), stati Online / Bozza / Programmata / Modifiche non pubblicate.
- Pulsanti per riga: Su / Giù, Sposta in… (solo destinazioni valide), Indirizzo… (avviso 301), Anteprima (`/_preview/<id>` in nuova scheda), Vedi online, Cestina (conferma; disattivato senza `content.publish` sulle pagine online).
- Nuova pagina: solo titolo e posizione ("In cima" o "Sotto…"); senza homepage: "Crea la homepage".
- `/admin/cestino`: elenco e Recupera (`parent_trashed` → "Recupera prima la pagina superiore").
- Il titolo si cambia nell'editor (5b). Sotto 1024 px azioni in un menu "⋯"; sotto 600 px solo consultazione (D-10).

### Struttura di `admin/`
```
admin/ package.json · package-lock.json · .npmrc · tsconfig.json · vite.config.ts · eslint.config.js · index.html
  scripts/check-dist.mjs     # la build fallisce con script/stili inline, data:, indirizzi esterni
  src/ main.tsx · App.tsx
    api/ (client, types, auth, pages, site) · session/ · router/ · shell/ · features/page-tree/ · ui/ · text/it.ts · styles/
    test/ setup.ts · fakeApi.ts      (test colocati *.test.ts(x))
```

### Dipendenze (D-89, versioni esatte + lockfile)
- Runtime: `react`, `react-dom`.
- Sviluppo: `vite`, `@vitejs/plugin-react`, `typescript`, `vitest`, `@vitest/coverage-v8`, `jsdom`, `@testing-library/react`, `@testing-library/dom`, `@testing-library/user-event`, `eslint`, `@eslint/js`, `typescript-eslint`, `eslint-plugin-react-hooks`.
- In 5b: TipTap (estensioni singole) e dnd-kit.
- No: router, TanStack Query, i18n, UI kit/Tailwind, librerie di icone, rjsf/ajv, MSW, Prettier.

### Backend (5a)
| File | Modifica |
|---|---|
| `app/config.py` | `ADMIN_DIST_DIR` con controlli; `SESSION_COOKIE_SAMESITE = "Strict"` (D-91) |
| `app/services/panel_assets.py`, `app/panel.py` | servire la build, CSP |
| `app/services/authors.py`, `app/services/errors.py` | `details.updated_by_name` nel 409 (D-92) |
| `app/api/admin/site.py` | `GET /api/admin/site` → `{name, url, locales, default_locale}` |
| `tests/security/test_golden_rule.py`, `tests/security/test_admin_source.py` | route pubbliche nuove; guardiano del sorgente del pannello (D-98) |
| `scripts/tasks.py`, `Makefile`, `.github/workflows/ci.yml` | comandi `admin-*`, job CI `admin` (D-96) |

### Sicurezza
Regola d'oro: nessun campo o upload di html/css/js/svg, route `/admin*` in sola lettura, nessun Jinja. CSP rigida + `check-dist.mjs`. Guardiano del sorgente (niente `dangerouslySetInnerHTML`, `innerHTML`, `eval`, token in storage, indirizzi esterni non motivati, `postMessage` verso `"*"`). `SameSite=Strict`. Accesso con `autocomplete` corretti, niente "ricordami", messaggi unici del server. Link esterni `noopener noreferrer`. Dev server solo su `127.0.0.1`.

### Test
- Pytest: route del pannello (index, 308, CSP, asset, traversal, 405, 503, `ConfigError`), `/admin-qualcosa` resta del sito, `/api/admin/site`, `updated_by_name`, cookie Strict, `tasks.py` senza npm.
- Vitest + Testing Library (soglia 80 %): client API, router, sessione (accesso, TOTP, nuovo accesso, logout), `tree.ts`, schermate Pagine e Cestino, accessibilità di base.
- CI: job `admin` su Linux e Windows (Node 24): `npm ci`, lint, test con copertura, build, `check:dist`.

### Ordine (TDD)
1. `tasks.py` + test · 2. `ADMIN_DIST_DIR` · 3. `panel_assets` + `panel` · 4. SameSite · 5. `updated_by_name` · 6. `/api/admin/site` · 7. guardiano · 8. impalcatura `admin/` + CI · 9. client API · 10. router · 11. sessione · 12. shell + UI + stili ThiasNET · 13. `tree.ts` · 14. schermata Pagine · 15. Cestino · 16. prova manuale · 17. docs · 18. review ECC.

## Rimandi
- Fase 6: azione rapida "banner avviso"; Fase 7: lingue nel pannello, azione "notizia".
- Fase 8: Docker con `npm ci && npm run build` + `check:dist`, Caddy per `/admin/assets/`, e2e completi, `npm audit` e action fissate a SHA, axe sul pannello.
- IDEE: nome visualizzato degli utenti, pannello in tedesco, tema scuro, trascinamento nell'albero, QR per il TOTP, altre scorciatoie, notifiche dei messaggi.

---

# 5b — Editor della pagina

Prodotto con `ecc:planner` il 2026-10-18 sul branch `phase-5b-editor` (partito da `phase-5-admin`).
Decisioni D-102 … D-115.

## Risposte di Thias (tutte le proposte)
1. **Salvataggio:** scritta piccola in alto ("Salvato alle 10:42", "Sto salvando…", avviso rosso se non riesce). → D-104
2. **Anteprima sul tablet:** pulsante "Modifica / Anteprima"; sul computer sempre affiancata. → D-107
3. **Aggiungi blocco:** riquadri con nome, piccolo disegno e una frase; disegni nostri, uguali per tutti i siti. → D-115
4. **Pubblica:** chiede conferma con l'indirizzo della pagina (in 5d qui arrivano i controlli D-09). → D-113

## Punti trovati prima di iniziare
1. `GET /pages/<id>/draft` senza bozza restituisce già il pubblicato (`version: 0`, `from_published`); stato e `pages.version` arrivano da `GET /pages/<id>`.
2. Titolo, layout e SEO stanno nel documento della bozza `{title, layout, seo, zones}`.
3. Due versioni: `publish` usa `draft_version`, `unpublish` usa `pages.version`; dopo la pubblicazione la bozza sparisce (`draft_version` torna 0).
4. L'editor salva solo il documento intero (`PUT /draft`): così l'`uid` lo crea il pannello (D-39).
5. In bozza il server rifiuta `pattern`, `safe-url`, `maxLength`, `enum`: un link scritto a metà farebbe fallire tutto il salvataggio → il pannello manda l'ultimo valore valido (D-104).
6. TipTap vuoto produce `<p></p>`: editor vuoto = campo assente.
7. `jsonify` ordina le chiavi: il catalogo perde l'ordine di campi, zone e varianti → `app.json.sort_keys = False`.
8. I campi degli schemi non hanno etichette italiane, gli `enum` nemmeno, le zone del tema `default` neppure → `title`/`description`/`x-enum-titles` negli schemi, `label` alle zone (D-106).
9. Miniature delle varianti da `/assets/<path>`: il catalogo dà `thumbnail_url` con versione.
10. `POST /_preview/<id>`: form con `csrf_token` e `document`; un errore CSRF lì oggi diventa JSON e l'iframe lo blocca → pagina HTML.
11. `preview.js` scorre a ogni `cms:highlight` e salva lo scroll solo su `beforeunload` → `scroll:false` e salvataggio mentre si scorre.
12. Inviare sempre allo stesso iframe riempie la storia del browser → iframe nuovo a ogni aggiornamento (D-107).
13. Media: `x-media: "file"` = tipo `document`; manca la lettura di più media per id; l'alt mancante blocca la pubblicazione (5b-2).

## Divisione (D-102)
- **5b-1** (questa PR): etichette e ordine del catalogo, anteprima live, modello del documento, annulla/ripristina, salvataggio automatico, form dagli schemi, zone e blocchi con pulsanti, varianti, titolo/tipo di pagina/SEO, TipTap, pubblica/ritira/scarta. Il campo media è in sola lettura.
- **5b-2** (PR successiva): scelta e caricamento dei media nell'editor, `GET /media?ids=`, trascinamento con dnd-kit, aiuti per video e mappa, primo e2e con `pytest-playwright` (Edge su Windows).

## Architettura (5b-1)
- `features/editor/model/`: funzioni pure su dati immutabili (`document`, `relayout`, `uid`, `history`, `draftSafe`, `errorPaths`), `autosave.ts` senza React con orologio iniettabile.
- Annulla/ripristina: una sola storia nel pannello, 100 passi, battute nello stesso campo unite entro 1 s, Ctrl+Z/Ctrl+Y e pulsanti (D-105).
- Salvataggio: 1,5 s dopo l'ultima modifica, una richiesta alla volta, subito uscendo e prima di pubblicare; 409 → scelta "Carica la sua versione" / "Tieni la mia"; dopo un nuovo accesso si risalva senza ricaricare (D-104).
- `features/editor/schema/`: validatore del client limitato alle parole chiave usate dagli schemi (guardiano), stessi percorsi e messaggi del server, casi condivisi con pytest (D-106).
- Anteprima: form nascosto verso un iframe nuovo a ogni aggiornamento (500 ms), scambio dopo `cms:ready`, messaggi solo dalla stessa origine e dall'iframe attivo; sul tablet pulsante Modifica/Anteprima (D-107).
- TipTap 3 con le sole estensioni di D-49, `injectCSS: false`, link con `rel="noopener noreferrer"` e indirizzi ammessi (D-108).
- Cambio del tipo di pagina: i blocchi seguono la zona con lo stesso nome o la prima che li ammette; quelli senza posto si elencano in una conferma (D-110).
- Pubblica: salva, conferma con l'indirizzo, `publish`; gli errori 422 diventano un elenco con "Vai al campo" (D-113).

## Dipendenze
- 5b-1: `@tiptap/core`, `@tiptap/react`, `@tiptap/pm` e le estensioni singole (document, paragraph, text, heading, bold, italic, link, list, blockquote, hard-break). Niente starter-kit né menu.
- 5b-2: `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`; Python di sviluppo `pytest-playwright`.

## Rimandi
- 5c: pagina Media completa, caricamento multiplo, `blob:` nella CSP, revisioni e programmazione nell'editor.
- 5d: controlli prima di pubblicare nella finestra di conferma (D-09), tour, "Chiedi a Thias", "Pubblica" da telefono.
- IDEE: anteprima a larghezza telefono, copia di blocchi tra pagine, chi sta modificando la pagina adesso.

---

# 5c — Libreria e amministrazione

Prodotto con `ecc:planner` il 2026-10-18 sul branch `phase-5c-admin` (partito da `phase-5b2-editor`).
Decisioni D-116 … D-130.

## Risposte di Thias (tutte le proposte)
1. **Messaggi del modulo contatti:** li leggono solo gli amministratori del cliente e Thias (sono dati personali). → D-126
2. **Cancellare i messaggi:** sì, uno alla volta con conferma (richieste dei visitatori). → D-126
3. **Password di un nuovo utente:** la sceglie chi lo crea (pulsante "Genera"), poi la persona la cambia se vuole. → D-123
4. **Punto focale:** clic sulla foto con due esempi di taglio (quadrato e largo). → D-119

## Punti trovati prima di iniziare
1. Il pannello scambia ogni 401 per sessione scaduta: una password attuale sbagliata nel Profilo (401 `invalid_password`) aprirebbe la finestra di nuovo accesso → D-127.
2. Messaggi: nessuna API e nessuno stato "letto" → migrazione `read_at`.
3. Revisioni: solo `author_id`, e un editor non può leggere gli utenti → nome di chi ha salvato e titolo dal server.
4. Programmazione: il fuso si converte nel pannello con `Intl` (su Windows Python non ha i fusi senza `tzdata`).
5. Media: manca lo spazio usato e il limite per file (`GET /media/usage`), il filtro "Senza cartella" e il numero di file per cartella; il punto focale rigenera le varianti (salvataggio con un pulsante).
6. Registro: niente filtri né nome di chi ha agito; mancano indici su `action` ed `entity`.
7. `update_user` scrive `user.updated` anche senza cambiamenti.

## Divisione (D-116)
- **5c-1 — Libreria e pagine:** pagina Media completa (cartelle, filtri, caricamento multiplo, dettaglio con punto focale, Sostituisci, Usato in, Elimina, spazio), `blob:` in `img-src`, versioni e programmazione nell'editor, badge nell'albero, chiavi stabili negli elenchi, Vimeo privato, e2e media e trascinamento.
- **5c-2 — Amministrazione:** API e schermata Messaggi, Utenti, Registro con filtri, Profilo, menu secondo i permessi, regola del 401.

## Rimandi
- 5d: QR per il codice a 6 cifre (se il test d'uso lo chiede), "Apri nella libreria" dal selettore.
- IDEE: esportazione e notifiche dei messaggi, "Riprova invio", azioni su più media, confronto tra versioni, invito via email, cambio password obbligatorio, fuso configurabile.
- Fase 8: conservazione del registro, axe sulle schermate nuove.
