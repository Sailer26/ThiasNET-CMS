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
- **7a — Raccolte (server e sito):** migrazione `0013` (`entries`, `entry_drafts`), schema dei campi generato da
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
