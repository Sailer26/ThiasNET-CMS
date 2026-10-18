# Passaggio di consegne — ThiasNET CMS (per una nuova sessione / nuovo account Claude)

Aggiornato: 2026-10-18. Leggi questo file **dopo** `CLAUDE.md` e prima di qualsiasi altra cosa.

## 1. Dove siamo
- Repository: https://github.com/Sailer26/ThiasNET-CMS (branch di default `main`)
- Cartella locale: `C:\Users\thias\progetti\ThiasNET CMS` (Windows 11, Python 3.12, Node 24, Git Bash)
- Identità git del repo: `Sailer26 <thias.nietli@gmail.com>` (impostata per-repo, non globale)
- **Fase 0 — Fondamenta:** chiusa e unita in `main`.
- **Fase 1 — Utenti e autenticazione:** chiusa e unita in `main` (PR #1, commit `e2ae055`). 235 test verdi, copertura 96.6 %, CI verde su Linux e Windows.
- **Fase 2 — Pagine e blocchi (backend):** chiusa e unita in `main` (PR #2).
- **Fase 3 — Rendering pubblico:** completata sul branch `phase-3-rendering` (764 test verdi, copertura 95 %, review ECC fatta, problemi alti e medi corretti). In attesa della PR verso `main`. Piano e scelte in `docs/PIANO-FASE-3.md`. Prossima: **Fase 4 — Media library**.
- Le decisioni di prodotto sono in `docs/DECISIONI.md` (D-01 … D-69). Prevalgono sugli altri documenti.

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
- La regola d'oro vieta anche chiamate di nome `touch` (come `Path.touch`): per questo la cache usa `page_cache.mark_changed()`.
- Nei template dei blocchi i campi con il nome di un metodo dei dizionari si leggono con `.get(...)` (es. `block.data.get("items")`): `block.data.items` è il metodo.
- Lo script della shell a volte rifiuta blocchi lunghi con virgolette (errore "unexpected EOF"): in quel caso scrivere lo script Python in un file dello scratchpad ed eseguirlo.
- `migrations/env.py` usa `fileConfig(..., disable_existing_loggers=False)`: altrimenti, dopo una migrazione nello stesso processo (test), i logger dell'app restano spenti.
- I test del kit in `tests/security/test_template_lock.py` su media (Fase 4) e settings (Fase 6) sono saltati con skip mirati: `test_golden_rule.py` fallisce se la route nasce e lo skip resta. Toglierli nella fase giusta.

## 5. Fase 3 — fatta
Piano, risposte di Thias (banner con scelta, Matomo, messaggi 12 mesi, anteprima solo dal pannello) e
dettagli in `docs/PIANO-FASE-3.md`; decisioni D-50 … D-69; rimandi alle fasi successive in ROADMAP.

## 6. Prossimo passo: Fase 4 — Media library
1. Branch `phase-4-media` da `main` (dopo il merge della PR della Fase 3).
2. Piano con `ecc:planner` (stesso formato di `docs/PIANO-FASE-3.md`), con al massimo 4 domande semplici per Thias.
3. Da collegare: `img()` e `media_url()` del renderer (oggi vuoti, D-57), `registry.media_ids` per i media in uso,
   `og:image`, link dei file scaricabili; attivare gli skip di `test_template_lock.py` sui media (Fase 4).
4. Test prima, poi codice, poi le tre review ECC in parallelo (`ecc:code-reviewer`, `ecc:python-reviewer`, `ecc:security-reviewer`
   con i controlli di `/check-template-lock`), correzioni, docs, push e link della PR per Thias.
