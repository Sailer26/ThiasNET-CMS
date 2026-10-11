# Roadmap — ThiasNET CMS

Una fase alla volta. Una fase è chiusa solo quando tutti i criteri sono spuntati e `make test` + `make lint` sono verdi.

## Fase 0 — Fondamenta
- [ ] Repo, `pyproject.toml`, `Makefile`, ruff/mypy, pre-commit, Docker dev
- [ ] App factory Flask, config per ambiente, SQLAlchemy + Alembic, SQLite WAL
- [ ] `services/theme.py`: carica e valida `theme.json` (JSON Schema); avvio fallisce se invalido
- [ ] `tests/security/test_template_lock.py` attivo (anche se alcune parti sono ancora `skip` dove le route non esistono)
- [ ] CI (GitHub Actions): test + lint

## Fase 1 — Utenti e autenticazione
- [ ] Modello `users`, ruoli owner/admin/editor, Argon2
- [ ] Login/logout, sessione, CSRF, rate limit login, TOTP opzionale
- [ ] Decoratore permessi + test per ogni ruolo
- [ ] Comando `flask create-owner`
- [ ] `audit_log` base

## Fase 2 — Pagine e blocchi (backend)
- [ ] Modelli pagine, blocchi, revisioni
- [ ] Registry blocchi + JSON Schema per i 13 blocchi base (incluso `hero`, D-11)
- [ ] Validazione zone/blocchi ammessi e varianti (`block_variants`) da `theme.json` (D-03)
- [ ] `users.can_publish` per editor (D-15); job `flask publish-scheduled` (D-16)
- [ ] Bozze autosave (`page_drafts`) separate dalla versione pubblicata (D-07)
- [ ] Sanitizzazione rich text (nh3) + test XSS
- [ ] API CRUD pagine/blocchi, riordino, bozza/pubblica/programma, ripristino revisione

## Fase 3 — Rendering pubblico
- [ ] Sandboxed Jinja, loader limitato al tema attivo, helper `img()` e `safe_html`
- [ ] Tema `default` completo (layout, partials, blocchi), accessibile e responsive
- [ ] Risoluzione path, 404 del tema, redirect, sitemap, robots, canonical
- [ ] Cache HTML + invalidazione
- [ ] Anteprima bozza per utenti loggati + endpoint anteprima live con `data-block-id` (D-02)
- [ ] Banner consenso cookie, video/mappe "clicca per caricare", analytics solo dopo consenso (D-06)
- [ ] Modulo contatti: invio SMTP, honeypot, rate limit, tempo minimo, `contact_messages` (D-05)

## Fase 4 — Media library
- [ ] Upload con verifica MIME sui byte, allowlist, limite dimensione, SVG rifiutati
- [ ] Re-encode, strip EXIF, varianti da `image_sizes`, focal point
- [ ] Cartelle, ricerca, alt obbligatorio, dedup sha256, blocco eliminazione se in uso

## Fase 5 — Pannello admin (React)
- [ ] Shell Vite+TS, login, layout, gestione errori/sessione scaduta
- [ ] Albero pagine, editor pagina con zone e blocchi drag&drop (dnd-kit), TipTap
- [ ] Anteprima live affiancata (iframe), click sul blocco → apre il form (D-02)
- [ ] Scelta varianti blocco da miniature (D-03)
- [ ] Autosave + annulla/ripristina (D-07)
- [ ] Media picker, gestione utenti (admin/owner), audit log (owner)
- [ ] Tour guidato al primo accesso, suggerimenti accanto ai campi, controllo prima di pubblicare, "Chiedi a Thias" (D-08, D-09)
- [ ] UI tutta in italiano, PC + tablet, azioni rapide da telefono (D-10)
- [ ] Test d'uso con un cliente vero (PREMORTEM #6)

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
