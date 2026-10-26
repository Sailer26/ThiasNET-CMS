# Piano Fase 7 — Raccolte e lingue (2026-10-24)

Decisioni D-147 … D-151. Piano di `ecc:planner`, risposte di Thias tutte sulle proposte.

## Risposte di Thias
1. **Raccolte:** solo le Notizie subito; gli Eventi quando un cliente li chiede. → D-148
2. **Indirizzo:** `/notizie/festa-del-paese`. → D-149
3. **Eventi passati:** spariscono dall'elenco, l'indirizzo resta. → D-150
4. **Lingue:** in questa fase, traduzione collegata; senza traduzione si va alla homepage della lingua. → D-151

## Punti trovati prima di iniziare
- `theme.json` del tema default dichiara `news` ed `events`; `theme.py` legge le raccolte ma nessuno le usa.
- `theme.schema.json` ammette nove tipi di campo, nessuno HTML.
- `latest_entries` è spento (`ENABLED_WIDGET_TYPES`, D-142); il suo schema esiste già.
- `pages.translation_group` esiste già (uuid a ogni pagina).
- Menu, widget, pagine e altro usano `theme.locales[0]` in vari punti (D-94): con la 7c un solo `panel_locale()`.

## Divisione (D-147)
- **7a — Raccolte (server e sito) (fatta, D-152):** migrazione `0013` (`entries`, `entry_drafts`), schema dei campi generato da
  `theme.json` e validato come i blocchi, bozza, pubblica, programma, ritira, cestino, versioni; API
  `/collections/<chiave>/entries` e `/entries/<id>…` con i permessi di oggi (D-48); pagina elenco (layout con
  `collection`) con paginazione `?p=`, dettaglio `entries/<chiave>.html`, helper `entry_list()` e
  `format_date()`; 301 se cambia l'indirizzo dell'elenco; sitemap; "Usato in" per i media; regola d'oro.
- **7b — Pannello:** schermata Notizie (elenco, editor dallo schema, salvataggio automatico, versioni,
  programmazione, controllo prima di pubblicare, anteprima), "Notizia" dal telefono (D-97), widget
  "ultime notizie" acceso.
- **7c — Lingue:** traduzioni collegate per pagine e notizie (migrazione `0014`), selettore lingua,
  `hreflang` e sitemap, lingua scelta nel pannello per albero, menu, widget e notizie.

## Ordine dei lavori della 7a
1. Tema: `per_page` delle raccolte e `collection` dei layout in `theme.schema.json`; `theme_lint` richiede
   `entries/<chiave>.html`; tema default con solo `news` (D-148) e layout `news_list`.
2. Modelli `app/models/entry.py`, migrazione `0013` (parità e indici parziali).
3. `app/services/collections.py`: schema dai campi, validazione bozza/pubblica.
4. `app/services/entries.py` e `entry_publishing.py` (anche nel comando `publish-scheduled`).
5. `media_refs` con le notizie.
6. API `app/api/admin/entries.py`.
7. `public_pages.resolve` per dettaglio, elenco paginato e 301; elenco senza sottopagine in `pages.py`.
8. Rendering: `EntryView`, `entry_list()`, `format_date()`, cache con il numero di pagina, notizie programmate.
9. Tema default: `layouts/news_list.html`, `entries/news.html`, CSS.
10. Sitemap; `test_template_lock.py` esteso; docs; review ECC; push.

## Rischi
- Indirizzo dell'elenco cambiato: le notizie lo seguono (301 per prefisso).
- Slug di una notizia uguale a una sottopagina: l'elenco non può avere sottopagine.
- Notizie programmate e cache: rinnovo come per i banner (D-146).
- Regola d'oro: i campi sono solo dati (testo, testo formattato con l'allowlist, media, url sicuri), mai template.

## Fase 7b — Notizie nel pannello (2026-10-25, fatta: D-157)

Decisioni D-153 … D-156. Piano di `ecc:planner`, risposte di Thias tutte sulle proposte.

### Risposte di Thias
1. **Foto dal telefono:** si sceglie ogni volta, fotocamera o galleria. → D-153
2. **Chi non può pubblicare, dal telefono:** salva come bozza. → D-154
3. **Ultime notizie:** 3 notizie con titolo e data nel piè di pagina. → D-155
4. **Anteprima:** affiancata come per le pagine. → D-156

### Lavori
- **Server:** raccolte nei dati del sito; versioni delle notizie con contenuto, autore e ripristino in bozza
  (D-40, D-42); "programmazione con modifiche più recenti"; `GET /entries/<id>/checks` con la stessa
  validazione di `publish` (D-135); anteprima `/_preview/entries/<id>`; widget `latest_entries` acceso con
  `collection` e `limit`, template nel tema.
- **Pannello:** pezzi comuni dell'editor resi generici (salvataggio automatico, cronologia, anteprima,
  versioni, conflitto); campi data e data/ora; voce di menu per raccolta; elenco con cestino; nuova notizia;
  editor della notizia; "Notizia" dal telefono; scelta della raccolta nel widget.
- **Test:** pytest per anteprima, controlli, versioni e widget; vitest per campi e schermate; un e2e; regola d'oro.

### Rischi
- Rendere generici i pezzi dell'editor senza rompere quello delle pagine: commit a parte, test delle pagine verdi.
- Dal telefono più passi non atomici: prima la foto, poi la notizia (una foto abbandonata resta in libreria).
- Nuova route di anteprima: meta-test dei permessi e review di sicurezza.

## Fase 7c — Lingue (2026-10-26)

Decisioni D-151 (presa prima), D-158 … D-161. Piano di `ecc:planner`, risposte di Thias tutte sulle proposte.

### Risposte di Thias
1. **Chi decide le lingue:** Thias nel tema; una lingua compare quando la sua homepage è online. → D-158
2. **Il pannello ricorda la lingua:** sì, su quel computer. → D-159
3. **Avviso "traduzione forse vecchia":** non ora, tra le idee. → D-160
4. **Cestino dell'originale:** le traduzioni restano. → D-161

### Lavori
- **Server:** indici unici (gruppo di traduzione, lingua) per pagine e notizie (migrazione `0014`);
  `POST`/`GET /pages/<id>/translations` e `/entries/<id>/translations` (copia della bozza, pagina superiore
  tradotta o primo livello, slug libero nella lingua); lingua del pannello in un punto solo per albero, menu,
  widget e notizie; `languages()` per il tema, `hreflang` e `x-default`, sitemap con le alternative; "ultime
  notizie" nella lingua della pagina (oggi sempre la prima: errore trovato dal piano); selettore nel tema default.
- **Pannello:** lingua scelta in alto e ricordata; schermate per lingua; riquadro "Traduzioni" negli editor;
  "Crea la homepage in …" quando una lingua è vuota.
- **Test:** pytest per servizio, API, rendering, sitemap e lingua del pannello; vitest; e2e; regola d'oro.

### Rischi
- Home per lingua mancante: la lingua resta nascosta finché la sua homepage non è online.
- Link interni copiati nella traduzione puntano ancora all'originale (idea in IDEE.md).
- I testi in romancio vanno rivisti da chi lo parla.
