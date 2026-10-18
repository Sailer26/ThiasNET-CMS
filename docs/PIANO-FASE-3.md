# Piano della Fase 3 — Rendering pubblico

Prodotto con `ecc:planner` il 2026-10-18 sul branch `phase-3-rendering`. Le decisioni sono
registrate in `docs/DECISIONI.md` (D-50 … D-68), che prevale su questo documento.

## Risposte di Thias (tutte le proposte)
1. **Banner cookie:** "Accetta tutto" e "Solo necessari" con lo stesso peso, più "Scegli" con due caselle (Video e mappe, Statistiche). Vale 12 mesi; si riapre dal link "Cookie" nel piè di pagina. → D-60
2. **Statistiche:** Matomo installato una volta sul server ThiasNET in Svizzera. → D-66
3. **Messaggi del modulo contatti:** conservati 12 mesi, poi cancellati da soli. → D-67
4. **Anteprima di pagine non pubblicate:** solo per chi ha accesso al pannello; niente link condivisibile (resta in IDEE). → D-68

## Punti trovati prima di iniziare
- Il tema `default` ha solo `theme.json`: mancano layout, partials, blocchi e assets.
- `TEMPLATE_CONSTRUCTS` in `tests/security/test_golden_rule.py` non elenca `ImmutableSandboxedEnvironment` né i loader di Jinja: va chiuso.
- `make_theme` in `tests/conftest.py` scrive miniature finte: con il controllo sui byte serve un PNG vero.
- Le varianti reali del tema `default` cambiano alcuni test della Fase 2 che si aspettano `variant = None`.

## Decisioni tecniche (sintesi, dettagli in DECISIONI)
- **D-50 Indirizzi e lingue:** la prima lingua del tema è senza prefisso (`/chi-siamo`), le altre con prefisso (`/de/ueber-uns`); `/it/...` → 301 senza prefisso; `/de` → 301 `/de/`; slash finale → 301 senza; caratteri fuori da `[a-z0-9/-]` o path > 255 → 404 senza query. Le route tecniche iniziano con `_`.
- **D-51 Cosa mostra il sito:** solo `published` e non cestinate; programmazioni scadute passano da `publishing.ensure_due`; `page_redirects` → 301 solo verso pagine online, senza catene, query string scartata.
- **D-52 Renderer unico:** un solo `ImmutableSandboxedEnvironment` (autoescape) in `app/services/render.py`, `FileSystemLoader([theme.directory], followlinks=False)`; mai `render_template` di Flask; ai template solo dati congelati costruiti dal renderer; nomi di template solo da costanti + nomi verificati contro il tema; il tema usa `render_zone()`/`render_block()`.
- **D-53 Contenuto vecchio rispetto al tema:** al rendering si rivalidano layout, zone, blocchi e varianti; ciò che non torna si omette o prende il default, con un avviso nel log; mai un 500. `safe_html` ripulisce sempre.
- **D-54 Cache HTML:** in memoria per worker (LRU 500 voci / 32 MB); invalidazione condivisa con `site_state.cache_generation` nel DB; `page_cache.mark_changed()` nella stessa transazione di pubblica, programmata, ritira, cestino, slug/spostamento, riordino; l'autosave no; niente cache per anteprima, pagine con modulo, 404, POST; ETag + 304.
- **D-55 Anteprima:** `GET /_preview/<id>` (bozza salvata) e `POST /_preview/<id>` (form con `document` JSON + `csrf_token`, inviato dal pannello con `target` sull'iframe); serve `content.edit`, altrimenti 404; `X-Frame-Options: SAMEORIGIN` e `frame-ancestors 'self'` solo qui, `no-store`, `noindex`; nessuna scrittura. `app/static/cms/preview.js` evidenzia i blocchi e comunica il click con `postMessage` verificando l'origine.
- **D-56 Helper del contratto:** `cms_head()`, `cms_body_end()`, `render_zone()`, `zone_has_blocks()`, `img()`, `media_url()`, `asset()`, filtro `safe_html`, `cms_text()`, `embed()`, `menu()`, `widget_area()`, `breadcrumbs`, `settings`.
- **D-57 Prima delle Fasi 4/6/7:** `img()` vuoto sul sito e segnaposto in anteprima; `media_url()` → `None`; `widget_area()` vuota; settings del tema = default di `theme.json`; impostazioni del sito da `.env` (`SITE_NAME`, `CONTACT_RECIPIENT`, `MATOMO_URL`, `MATOMO_SITE_ID`) tramite `site_settings.current()`; hreflang e selettore lingua in Fase 7.
- **D-58 Menu automatico:** `menu("main")` = homepage + pagine di primo livello pubblicate, per `sort`, fino alla Fase 6.
- **D-59 Colori:** `GET /_vars.css` con sole variabili CSS validate (niente `<style>` inline, compatibile con la CSP).
- **D-60 Consenso:** cookie `cms_consent` scritto da `consent.js` (mai letto dal server: cache uguale per tutti); banner prodotto dal CMS; video e mappe sempre segnaposto con "Carica" + link esterno; YouTube via `youtube-nocookie.com`, Vimeo con `dnt=1`, mappe OpenStreetMap; iframe solo verso host in allowlist; statistiche solo dopo consenso.
- **D-61 Modulo contatti:** `POST /_contact` senza CSRF (pagine anonime) ma con controllo `Origin` contro `SITE_URL`, token firmato (min 3 s, max 6 h), body ≤ 16 KB, honeypot, limiti 3/10 min e 10/24 h per IP (/64 IPv6) e 50/ora per sito, IP solo come HMAC; salvataggio prima dell'invio, email solo testo con `Reply-To` validato; ritentativi con `flask send-contact-messages`.
- **D-62 SEO:** `SITE_URL` obbligatorio in produzione; canonical e sitemap da `SITE_URL`, mai dall'header Host; `robots.txt` aperto solo in produzione; `noindex` toglie dalla sitemap.
- **D-63 theme-check:** errori per template mancanti o che non compilano, avvisi per varianti di blocchi mai ammessi; miniature controllate sui byte (PNG `89 50 4E 47`, JPEG `FF D8 FF`, WebP `RIFF....WEBP`).
- **D-64 Varianti reali del tema default:** hero (`image_full`, `split`), text_image (`image_left`, `image_right`, `dark`), cta (`light`, `accent`, `dark`), quote (`simple`, `highlight`), gallery (`grid_3`, `grid_4`), con miniature PNG generate da `scripts/make_variant_thumbnails.py`.
- **D-65 Errori:** 404 dal tema (`layouts/404.html`) con ripiego testuale; 500 come pagina fissa del CMS.

## Modello dati
- `0005_site_state`: `site_state(id PK = 1, cache_generation, updated_at)`.
- `0006_contact_messages`: `contact_messages(id, form_page_id FK SET NULL, block_uid, locale, name, email, phone, message, ip_hash, created_at, sent_at, send_attempts, last_error)` con indici su `(ip_hash, created_at)`, `created_at`, `sent_at`.

## Moduli (in ordine)
1. Config del sito (`app/config_site.py`), `.env.example`, variabili isolate nei test.
2. Miniature sui byte (`services/theme.py`), `FAKE_PNG` nei test, `scripts/make_variant_thumbnails.py`, varianti del tema `default`.
3. `services/render.py`, `render_context.py`, `render_helpers.py`, `public_texts.py`, `site_settings.py`.
4. `services/public_pages.py`: `split_locale`, `resolve`, `public_url`, `breadcrumbs`, `auto_menu`, `sitemap_entries`.
5. `services/page_cache.py` + `mark_changed()` in pubblicazione e pagine.
6. `services/seo.py`.
7. `services/preview.py`.
8. `services/contact_form.py`, `services/mailer.py`, `app/cli_contact.py`.
9. Blueprint `app/public/` (pagine, sitemap, robots, assets, `_vars.css`, anteprima, contatti, header, errori).
10. `app/static/cms/consent.js` e `preview.js`.
11. Tema `default`: layout, partials, 13 blocchi, `site.css`, `site.js`, accessibilità WCAG 2.1 AA.
12. `services/theme_lint.py` per theme-check.
13. Docs.

## Route pubbliche
| Metodo e path | Accesso | Risposte |
|---|---|---|
| GET `/`, `/<path>` | pubblico | 200 · 301 · 304 · 404 (tema) |
| GET `/sitemap.xml`, `/robots.txt` | pubblico | 200 |
| GET `/assets/<file>` | pubblico, solo estensioni ammesse | 200 · 404 |
| GET `/_vars.css` | pubblico | 200 |
| GET/POST `/_preview/<id>` | `content.edit` (+ CSRF sul POST) | 200 · 403 · 404 · 413 · 422 |
| POST `/_contact` | pubblico (Origin + token) | 303 · 403 · 413 · 422 · 429 |
| CLI `send-contact-messages`, `purge-contact-messages` | cron | exit 0/1 |

## Test da scrivere per primi
Guardiani della regola d'oro (sandbox, allowlist, route pubbliche note, tema invariato), test del kit `test_jinja_in_content_is_not_executed` attivato, sandbox, rendering dei 13 blocchi e casi D-53, accessibilità di base, risoluzione dei percorsi, cache, sito (canonical, sitemap, robots, 404, ETag, header), anteprima, contatti, mailer e config, miniature e theme-check.

## Rimandi da registrare in ROADMAP
- Fase 4: `og:image` e il vero `img()`.
- Fase 5: messaggi di contatto nel pannello; test degli script del CMS.
- Fase 6: menu e widget configurati; impostazioni dal DB.
- Fase 7: hreflang e selettore lingua.
- Fase 8: CSP con host esterni (Matomo, iframe), axe e Lighthouse automatici, dati strutturati, theme-check nel build Docker.
