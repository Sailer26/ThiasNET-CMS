# Passaggio di consegne — ThiasNET CMS (per una nuova sessione / nuovo account Claude)

Aggiornato: 2026-10-19. Leggi questo file **dopo** `CLAUDE.md` e prima di qualsiasi altra cosa.

## 1. Dove siamo
- Repository: https://github.com/Sailer26/ThiasNET-CMS (branch di default `main`)
- Cartella locale: `C:\Users\thias\progetti\ThiasNET CMS` (Windows 11, Python 3.12, Node 24, Git Bash)
- Identità git del repo: `Sailer26 <thias.nietli@gmail.com>` (impostata per-repo, non globale)
- **Fase 0 — Fondamenta:** chiusa e unita in `main`.
- **Fase 1 — Utenti e autenticazione:** chiusa e unita in `main` (PR #1, commit `e2ae055`). 235 test verdi, copertura 96.6 %, CI verde su Linux e Windows.
- **Fase 2 — Pagine e blocchi (backend):** chiusa e unita in `main` (PR #2).
- **Fase 3 — Rendering pubblico:** chiusa e unita in `main` (PR #3).
- **Fase 4 — Media library:** completata sul branch `phase-4-media` (870 test verdi, copertura 94 %). PR verso `main` da aprire/unire.
- **Fase 5a — Pannello: telaio, accesso, pagine:** completata sul branch `phase-5-admin`, partito da `phase-4-media`.
- **Fase 5b-1 — Editor della pagina:** completata sul branch `phase-5b-editor`, partito da `phase-5-admin` (1036 test Python, 170 del pannello, review ECC fatta). **Nessuna delle PR 4/5a/5b-1 risulta unita in `main`**: la PR da `phase-5b-editor` verso `main` le contiene tutte. Prossima: **5b-2**.
- **Fase 5b-2 — Media nell'editor, trascinamento, aiuti, primo e2e:** completata sul branch `phase-5b2-editor`, partito da `phase-5b-editor` (1059 test Python, 205 del pannello, 1 e2e, review ECC fatta). La PR da `phase-5b2-editor` verso `main` contiene anche le Fasi 4, 5a e 5b-1 se non sono ancora unite. Prossima: **5c**.
- **Fase 5c-1 — Libreria e pagine:** completata sul branch `phase-5c-admin`, partito da `phase-5b2-editor` (1076 test Python, 227 del pannello, 3 e2e, review ECC fatta). Prossima: **5c-2**.
- **Fase 5c-2 — Amministrazione:** completata sul branch `phase-5c2-admin`, partito da `phase-5c-admin` (1103 test Python, 249 del pannello, 4 e2e, review ECC fatta). `origin/main` è ancora alla PR #3: la PR da `phase-5c2-admin` verso `main` contiene tutte le fasi dalla 4 in poi. Prossima: **5d**.
- **Fase 5d-1 — Controlli e assistenza:** completata sul branch `phase-5d-help`, partito da `phase-5c2-admin` (1130 test Python, 259 del pannello, 4 e2e, review ECC fatta). La PR da `phase-5d-help` verso `main` contiene tutte le fasi dalla 4 in poi. Prossima: **5d-2 — Guida e rifiniture** sul branch `phase-5d2-help`.
- Le decisioni di prodotto sono in `docs/DECISIONI.md` (D-01 … D-137). Prevalgono sugli altri documenti.

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
- **Regola d'oro:** `tests/security/test_golden_rule.py` vieta in `app/` qualsiasi chiamata di nome `copy`, `remove`, `move`, `rename`, `save`, `write_text`, `mkdir`… (allowlist: `database.py` → `mkdir`; `media_storage.py` → `mkdir`/`open`/`unlink`/`rmdir`; `media_images.py` → `save` solo in un `BytesIO`) e la costruzione di template (`Template`, `Environment`, `from_string`…). Quindi: niente `dict.copy()` o `list.remove()`; usare comprehension/`copy.deepcopy`; nominare le funzioni `move_page`, `trash_page`, `store_draft`. In Fase 3 l'`Environment` del renderer va aggiunto all'allowlist.
- **pre-commit** fa girare mypy su tutto il progetto: commit parziali con moduli che dipendono da file non ancora aggiunti falliscono. Fare commit coerenti (o un commit unico per l'area).
- `mixed-line-ending` di pre-commit corregge file con CRLF e fa fallire il commit: rifare `git add` e ricommittare.
- Test: la fixture `app` crea il DB in memoria con `create_all` e **non tiene il contesto attivo** durante le richieste (altrimenti `g`/utente loggato verrebbero condivisi). Usare `make_user(app, …)`, `api_client(app)`, `login(...)`, `adopt_csrf(...)` da `tests/helpers.py` e la fixture `login_as(role)`.
- Le migrazioni sono scritte a mano; `tests/unit/test_models.py::test_migrations_match_models` verifica la parità con i modelli. Gli indici parziali non sono confrontati da `compare_metadata`: serve un test dedicato.
- Ogni route `/api/admin/*` deve avere `@require_permission(...)` o `@public` (meta-test `tests/api/test_route_permissions.py`).
- Script Python che scrivono file su Windows: usare `newline="\n"` (altrimenti CRLF e pre-commit fallisce). Nei testi passati agli strumenti di scrittura gli escape Unicode possono diventare caratteri invisibili veri: nei sorgenti usare `chr(0x...)`.
- `.gitignore` esclude solo `/data/` della radice (database): `app/data/` (password comuni) è nel repository.
- La regola d'oro vieta anche chiamate di nome `touch` (come `Path.touch`): per questo la cache usa `page_cache.mark_changed()`.
- Nei template dei blocchi i campi con il nome di un metodo dei dizionari si leggono con `.get(...)` (es. `block.data.get("items")`): `block.data.items` è il metodo.
- Lo script della shell a volte rifiuta blocchi lunghi con virgolette (errore "unexpected EOF"): in quel caso scrivere lo script Python in un file dello scratchpad ed eseguirlo.
- `migrations/env.py` usa `fileConfig(..., disable_existing_loggers=False)`: altrimenti, dopo una migrazione nello stesso processo (test), i logger dell'app restano spenti.
- I test del kit in `tests/security/test_template_lock.py` sui settings (Fase 6) sono saltati con skip mirati: `test_golden_rule.py` fallisce se la route nasce e lo skip resta. Quelli sui media sono attivi dalla Fase 4.
- I commit vanno fatti con la `.venv` nel `PATH` (`export PATH="$PWD/.venv/Scripts:$PATH"`): gli hook di pre-commit mypy e template-lock usano il `python` del sistema, che non ha le dipendenze.
- Pillow deve avere WebP: senza, l'app non parte (D-84). I test dei media usano `tests/media_fixtures.py`.

## 5. Fasi 3 e 4 — fatte
- Fase 3: piano e risposte di Thias (banner con scelta, Matomo, messaggi 12 mesi, anteprima solo dal pannello)
  in `docs/PIANO-FASE-3.md`; decisioni D-50 … D-69.
- Fase 4: piano e risposte (solo PDF oltre alle immagini, 15 MB per file e 5 GB per sito, anche gli editor
  eliminano i media non usati, "Sostituisci file" mantiene l'indirizzo) in `docs/PIANO-FASE-4.md`; decisioni D-70 … D-85.
- Rimandi alle fasi successive in ROADMAP.

## 6. Fase 5a — fatta
Risposte di Thias (tutte le proposte): marchio ThiasNET, albero con pulsanti, subito le pagine, nuova pagina con il
solo titolo. Decisioni D-86 … D-100. Comandi del pannello: `python scripts/tasks.py admin-install|admin-dev|admin-build|admin-test|admin-lint`.
- Sul PC di Thias la porta 5000 può essere occupata da un altro progetto: per provare `flask --app app run --port 5050`
  (con `APP_ENV=development`) dopo `admin-build`, poi `http://localhost:5050/admin/`.
- Lo strumento Bash di Claude rifiuta comandi con molti apostrofi (testi italiani): scrivere i file con uno script Python
  nello scratchpad (sezioni `=== percorso ===`).

## 7. Fase 5b-1 — fatta
Risposte di Thias (tutte le proposte): scritta piccola per il salvataggio, Modifica/Anteprima sul tablet, riquadri
con disegno per "Aggiungi blocco", conferma prima di pubblicare. Provata nel browser con la build vera: accesso,
nuovo blocco, testo, salvataggio, anteprima, pubblicazione (il testo compare sul sito), storia del browser intatta.
- Per provare in locale: utente di prova in `data/dev-credentials.txt` (cartella ignorata da git), server con
  `APP_ENV=development .venv/Scripts/python -m flask --app app run --port 5050` dopo `tasks.py admin-build`.
- TipTap nei test jsdom: si provano schema e HTML (`richtext/extensions.test.ts`), non la scrittura a tastiera.
- Gli script statici del CMS (`preview.js`, `consent.js`) si provano in `admin/src/test/static/` con jsdom.

## 8. Fase 5b-2 — fatta
- `python scripts/tasks.py e2e` (dopo `admin-build`) apre Edge, fa accesso → homepage → testo → anteprima → annulla → pubblica.
  Gli e2e sono esclusi dalla suite normale (`-m 'not e2e'` in `pyproject.toml`); in CI c'è un job Linux con Chromium.
- I media nell'editor passano da `MediaProvider` (`admin/src/features/media-picker/`): un'unica lettura `?ids=` a gruppi di 100.

## 9. Fase 5c — fatta
- 5c-1: pagina Media, versioni e programmazione nell'editor (ora svizzera con `Intl`, `siteTime.ts`).
- 5c-2: `admin/src/features/admin/` (Messaggi, Utenti, Registro, Profilo), migrazione `0008` (`read_at` dei
  messaggi, indici del registro), permesso `messages.view`. Gli e2e hanno anche la fixture `live_app` (l'app del
  server e2e) per preparare dati che il pannello non crea, come i messaggi.
- Dopo un nuovo accesso il pannello resta sull'indirizzo di prima (anche il profilo): negli e2e controllare quello.

## 10. Fase 5d-1 — fatta
- Controllo prima di pubblicare: `app/services/prepublish.py`; bloccanti da `publishing.problems` (stessa
  funzione di `publish`), avvisi `seo_empty`, `page_empty`, `link_broken`. Nel pannello `WarningList` e
  `features/page-tree/PhonePublish.tsx`.
- "Chiedi a Thias": `app/services/support.py`, migrazione `0009`, variabile `SUPPORT_EMAIL` (in `.env.example`),
  cron `flask send-support-requests` (ogni 10 minuti) e `flask purge-support-requests` (ogni giorno).
- Trappola: `ruff format`/`ruff check --fix` lanciati con il percorso `migrations/` esplicito toccano anche le
  migrazioni vecchie (escluse dalla configurazione): lanciarli su `app tests` o senza percorso.

## 11. Prossimo passo: Fase 5d-2 — Guida e rifiniture
1. Branch `phase-5d2-help` da `phase-5d-help` (o da `main` se le PR sono unite). Il piano c'è già
   (`docs/PIANO-FASE-5.md`, sezione 5d-2) e le domande sono state fatte (D-133).
2. `POST /me/tour`, tour di 5 passi con `data-tour`, menu Aiuto (Chiedi a Thias, Rifai il tour), suggerimenti
   mancanti, rimandi della 5c-2 e 5d-1 (vedi ROADMAP), "Apri nella libreria", e2e, `docs/TEST-USO.md`.
3. Test prima, codice, review ECC in parallelo, docs, push, link della PR.
