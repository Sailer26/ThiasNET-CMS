# CLAUDE.md — ThiasCMS

CMS proprietario di ThiasNET per i siti dei clienti (PMI, comuni, associazioni in Ticino/Grigioni).
Leggi SEMPRE prima di lavorare: `docs/PRD.md`, `docs/ARCHITETTURA.md`, `docs/TEMPLATE-CONTRACT.md`, `docs/ROADMAP.md`.

## Regola d'oro (non negoziabile)
**Il template (tema) non è modificabile dal pannello admin, da nessun ruolo.**
- I temi vivono solo nel filesystem in `themes/<nome>/` e cambiano solo via git + deploy (da Thias).
- Nessuna route, API, upload o impostazione può scrivere in `themes/`, caricare template, CSS o JS, o eseguire Jinja fornito dall'utente.
- Dal pannello si modificano solo: contenuti, blocchi nelle zone dichiarate dal tema, media, widget, menu e le sole impostazioni esposte in `theme.json > settings`.
- Ogni PR deve far passare `tests/security/test_template_lock.py`. Se un task sembra richiedere di violare questa regola: FERMATI e chiedi.

## Stack
- Backend: Python 3.12, Flask 3, SQLAlchemy 2, Flask-Migrate (Alembic), SQLite (WAL) in dev / PostgreSQL opzionale in prod
- Auth: Flask-Login, Argon2 (argon2-cffi), CSRF (Flask-WTF), TOTP opzionale per owner/admin
- Sito pubblico: Jinja2 SSR (autoescape ON), cache pagine
- Admin: React + Vite + TypeScript in `admin/`, TipTap (rich text), dnd-kit (drag&drop blocchi), comunica con `/api/admin/*`
- Media: Pillow (re-encode, strip EXIF, varianti WebP), nh3 per sanitizzare HTML
- Test: pytest (+ pytest-cov), Playwright per e2e
- Deploy: Docker, gunicorn, Caddy

## Struttura
```
app/            # Flask: __init__ (factory), config, models/, api/, public/, services/, blocks/
admin/          # React SPA del pannello
themes/default/ # tema di riferimento (theme.json, layouts/, partials/, blocks/, assets/)
migrations/
tests/          # unit/, api/, security/, e2e/
docs/
```

## Convenzioni
- Codice e identificatori in inglese; UI admin, messaggi e docs in italiano.
- Logica in `app/services/`, mai nelle route. Route sottili.
- Ogni blocco ha: schema JSON (validazione server), template Jinja nel tema, editor React.
- Contenuto dei blocchi validato lato server contro lo schema. Mai fidarsi del client.
- Rich text: solo allowlist nh3 (p, h2–h4, strong, em, a[href], ul, ol, li, blockquote). Niente blocco "HTML libero".
- Ogni modifica a pagine/widget/menu crea una revisione e una riga in `audit_log`.
- Migrazioni Alembic per ogni cambio schema. Mai `db.create_all()` fuori dai test.
- Multilingua (`locale`) presente nel modello dati fin dall'inizio (it di default; de, rm, en possibili).

## Workflow (con ECC)
1. Una fase della ROADMAP alla volta. Inizia con il piano (`/plan` di ECC), poi aspetta conferma.
2. TDD: test prima, poi implementazione (`/tdd`).
3. Prima di chiudere una fase: test verdi, review (`/code-review`), review sicurezza sulle route nuove, aggiorna `docs/ROADMAP.md` spuntando i criteri.
4. Commit piccoli, messaggi in italiano, formato `tipo(ambito): descrizione`.

## Comandi
- `make dev` · `make test` · `make lint` (ruff + mypy + eslint) · `make migrate` · `make seed`
- Comandi progetto: `/fase N`, `/nuovo-blocco <nome>`, `/check-template-lock`

## Non fare
- Non aggiungere dipendenze senza motivarle.
- Non creare endpoint per upload/modifica di file `.html`, `.jinja`, `.css`, `.js`, `.svg`.
- Non leggere né stampare `.env`.
