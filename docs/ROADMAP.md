# Roadmap — ThiasCMS

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
- [ ] Registry blocchi + JSON Schema per i 12 blocchi base
- [ ] Validazione zone/blocchi ammessi da `theme.json`
- [ ] Sanitizzazione rich text (nh3) + test XSS
- [ ] API CRUD pagine/blocchi, riordino, bozza/pubblica/programma, ripristino revisione

## Fase 3 — Rendering pubblico
- [ ] Sandboxed Jinja, loader limitato al tema attivo, helper `img()` e `safe_html`
- [ ] Tema `default` completo (layout, partials, blocchi), accessibile e responsive
- [ ] Risoluzione path, 404 del tema, redirect, sitemap, robots, canonical
- [ ] Cache HTML + invalidazione
- [ ] Anteprima bozza per utenti loggati

## Fase 4 — Media library
- [ ] Upload con verifica MIME sui byte, allowlist, limite dimensione, SVG rifiutati
- [ ] Re-encode, strip EXIF, varianti da `image_sizes`, focal point
- [ ] Cartelle, ricerca, alt obbligatorio, dedup sha256, blocco eliminazione se in uso

## Fase 5 — Pannello admin (React)
- [ ] Shell Vite+TS, login, layout, gestione errori/sessione scaduta
- [ ] Albero pagine, editor pagina con zone e blocchi drag&drop (dnd-kit), TipTap
- [ ] Media picker, gestione utenti (admin/owner), audit log (owner)
- [ ] UI tutta in italiano, utilizzabile da tablet

## Fase 6 — Widget, menu, impostazioni
- [ ] Widget per area con visibilità per pagina
- [ ] Menu per posizione, drag&drop, profondità massima
- [ ] Impostazioni sito + settings del tema generate da `theme.json` (form dinamico tipizzato)

## Fase 7 — Collezioni e multilingua
- [ ] Collezioni da `theme.json` (news, eventi), listing paginato, dettaglio
- [ ] Traduzioni collegate, selettore lingua, hreflang

## Fase 8 — Produzione
- [ ] Dockerfile multi-stage, docker-compose con Caddy, `themes/` read-only
- [ ] Backup/restore DB+media, healthcheck, log strutturati
- [ ] CSP e security header, test e2e Playwright dei flussi principali
- [ ] Documentazione `docs/DEPLOY.md` e `docs/NUOVO-TEMA.md`
