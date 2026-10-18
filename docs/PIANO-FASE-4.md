# Piano della Fase 4 — Media library

Prodotto con `ecc:planner` il 2026-10-18 sul branch `phase-4-media`. Le decisioni stanno in
`docs/DECISIONI.md` (D-70 … D-85), che prevale su questo documento.

## Risposte di Thias (tutte le proposte)
1. **Tipi di file:** foto + **solo PDF** (Word/Excel si salvano come PDF). → D-70
2. **Dimensioni:** **15 MB per file, 5 GB in tutto per sito**; oltre: "Spazio esaurito, contatta Thias". → D-71
3. **Eliminare:** **anche gli editor**, solo file non usati da nessuna pagina (il pannello mostra quali). → D-83
4. **Sostituire:** **sì, "Sostituisci file"** con lo stesso indirizzo (i link ai PDF restano validi). → D-85

## Punti trovati prima di iniziare
- `_is_write_mode` in `test_golden_rule.py` segnala ogni `open` in scrittura senza consultare l'allowlist: la condizione diventa `name == "open" and _is_write_mode(call) and (rel, "open") not in WRITE_ALLOWLIST`.
- Nomi vietati anche per Pillow: `Image.save` (vietata: unica eccezione motivata), `Image.copy()`; usare `crop()`/`resize()` che restituiscono immagini nuove; non usare `thumbnail()` (modifica sul posto). Nelle righe con `.save(` o `open(` non deve comparire la parola "theme" (controllo riga per riga del kit).
- `_media_ids` in `services/blocks.py` scende solo in `dict`/`list`: i `BlockView` hanno `MappingProxyType`/`tuple` → accettare `Mapping`/`Sequence` (non `str`).
- `seo.og_image_media_id` esiste già: conta come "in uso" e serve per `og:image`.
- Il blocco `image` non ha alt: l'alt sta sul media (coerente con D-09).
- `files.html` mostra solo l'etichetta: serve l'helper `media_file()` (nome, formato, peso).
- Se un deploy cambia `image_sizes`, i media vecchi non hanno le varianti nuove: ripiego nel renderer + `flask media-variants`.
- `EXPECTED_PUBLIC_ROUTES` deve includere `/media/...`; `RESERVED_SEGMENTS` e D-45 riservano già `media`.
- `tests/conftest.py::_isolated_environment` deve impostare `MEDIA_ROOT` su una cartella temporanea per ogni test.

## Decisioni tecniche (sintesi)
- **D-70 Tipi dai byte:** JPEG `FF D8 FF`, PNG `89 50 4E 47 0D 0A 1A 0A`, WebP `RIFF....WEBP`, GIF `GIF87a/GIF89a` (solo il primo fotogramma), PDF `%PDF-`. Estensione e Content-Type del browser ignorati; tutto il resto 415 `unsupported_type` (SVG, HTML, HEIC, AVIF, travestiti). Pillow apre con `formats=[tipo]`; decodifica fallita → 422.
- **D-71 Limiti:** un file per richiesta; 413 oltre `MAX_UPLOAD_MB` (15); `MEDIA_MAX_PIXELS` 40 MP (controllo dopo `Image.open`, prima di `load()`), `DecompressionBombWarning` come errore; `MEDIA_QUOTA_MB` 5120 → 507 `storage_full`.
- **D-72 Re-encode:** `exif_transpose`, ICC → sRGB (se illeggibile si scarta), via EXIF/ICC/XMP/commenti, CMYK/16 bit → RGB/RGBA; master al massimo 3840 px; JPEG q88 progressivo, PNG ottimizzato, WebP q85, GIF → PNG; sempre in `io.BytesIO`.
- **D-73 Varianti:** WebP q80; per ogni `image_sizes` larghezze {w, 2w} limitate dal master, mai ingrandire; `ratio` → ritaglio centrato sul punto focale; varianti del core `_panel` (400 px) e `_og` (1200×630); nomi `r<rev>-<size>-<w>.webp`, `r<rev>-master.<ext>`; `flask media-variants` genera le mancanti, il renderer usa la più vicina.
- **D-74 Archivio:** solo `app/services/media_storage.py`; radice `MEDIA_ROOT` (sviluppo `data/media`, test cartella temporanea, obbligatoria in produzione); `ConfigError` se dentro `THEMES_DIR`, dentro `app/` o antenato; percorso `<root>/<key[:2]>/<key>/<nome generato>`, `key = secrets.token_hex(16)`, nomi da regex + `resolve()`/`is_relative_to`; scrittura `open(path, "xb")`; allowlist: `media_storage.py` (`mkdir`, `open`, `unlink`, `rmdir`), `media_images.py` (`save` solo su BytesIO, test AST); upload: file prima del commit e cancellati se il commit fallisce; eliminazione: file dopo il commit, errori solo nel log.
- **D-75 Distribuzione `GET /media/<key>/<file>`:** solo file della revisione corrente di un media esistente (altrimenti 404); `nosniff` + `Content-Security-Policy: default-src 'none'; sandbox`; Content-Type dal CMS; immagini `public, max-age=31536000, immutable`; PDF a indirizzo stabile `/media/<key>/file.pdf`, `max-age=300` + ETag, sempre `attachment` con il nome originale.
- **D-76 Doppioni:** sha256 dei byte caricati (indice unico); doppione → 200 col media esistente e `meta.duplicate = true`; gara (IntegrityError) → quello esistente; sostituzione con un file uguale a un altro media → 409 `duplicate`.
- **D-77 Alt:** campo `alt` ≤ 250; si carica anche senza; filtro "manca il testo alternativo"; pubblicare/programmare bloccato se un'immagine usata (blocchi + og_image) non ha alt; non si svuota l'alt di un'immagine usata da pagine online o programmate (422).
- **D-78 Riferimenti:** `x-media` = `"image"` (image, gallery, hero, text_image) o `"file"` (files); a pubblica/programma/publish-scheduled si controllano esistenza, tipo e alt (`media_missing`, `media_not_image`, `alt_missing`) dentro il 422 `invalid_content`; in bozza e anteprima nessun controllo; `media_refs.check_document()` chiamato da `publishing`.
- **D-79 In uso:** pagina non cestinata con il media nei blocchi pubblicati, in `seo_json`, nella bozza o nella revisione programmata; DELETE → 409 `media_in_use` con `details` [{page_id, title, path, where}] (max 50); revisioni storiche e cestino non bloccano; calcolo su richiesta con fonti estendibili.
- **D-80 Punto focale:** `focal_x`/`focal_y` 0–100 (default 50); cambio → `file_rev + 1` e varianti nuove; nell'HTML solo classi `cms-img cms-fx-N cms-fy-N` (N = 0…10) definite in `app/static/cms/media.css`, collegato da `cms_head()`.
- **D-81 Helper:** `img(media_id, size="content", sizes=None, eager=False, css_class=None)` → `<img src srcset sizes width height alt loading decoding class>`; `media_url(id)`; `media_file(id)` → `{url, name, ext, size_label}`; `cms_head()` con `og:*` e `twitter:card`; immagine OG = `seo.og_image_media_id`, altrimenti la prima immagine della pagina.
- **D-82 Cartelle e ricerca:** max 3 livelli, nome 1–80 unico per cartella madre (senza maiuscole/accenti; indice parziale nella radice); si elimina solo vuota (409 `folder_not_empty`); niente cicli; ricerca `q` su `search_key` normalizzata; filtri `folder_id`, `kind`, `missing_alt`; più recenti prima; paginazione standard.
- **D-83 Permessi, versioni, audit, cache:** tutto con `content.edit` (anche eliminare, scelta di Thias), controllato nel service; `media.version` su PATCH/DELETE/sostituzione (409 `version_conflict`); audit `media.uploaded|updated|file_replaced|deleted`, `media_folder.created|renamed|moved|deleted`; `page_cache.mark_changed()` per alt/punto focale/nome, sostituzione, eliminazione.
- **D-84 Dipendenza:** `Pillow==13.0.0`; WebP obbligatorio (`features.check("webp")` all'avvio); niente AVIF/HEIC.
- **D-85 Sostituzione:** `POST /api/admin/media/<id>/file`, stesso id e tipo, `file_rev + 1`, controlli D-70/D-71, file vecchi cancellati dopo il commit.

## Modello dati — migrazione `0007_media`
```
media_folders(id PK, parent_id FK media_folders RESTRICT NULL, name VARCHAR(80), name_key VARCHAR(80),
              created_at, updated_at)
  UNIQUE(parent_id, name_key) + UNIQUE parziale (name_key) WHERE parent_id IS NULL
media(id PK, storage_key CHAR(32) UNIQUE, kind [image|document], mime VARCHAR(40), ext VARCHAR(5),
      original_name VARCHAR(200), search_key VARCHAR(500), size_bytes BIGINT, sha256 CHAR(64) UNIQUE,
      width INT NULL, height INT NULL, alt VARCHAR(250) DEFAULT '', focal_x SMALLINT DEFAULT 50,
      focal_y SMALLINT DEFAULT 50, variants_json JSON, file_rev INT DEFAULT 1, version INT DEFAULT 1,
      folder_id FK media_folders RESTRICT NULL, created_by/updated_by FK users SET NULL, created_at, updated_at)
  INDEX(folder_id), INDEX(created_at); CHECK focal 0–100
```
`variants_json`: `{"master": {...}, "sizes": {"card": [{"w":640,"h":480,"file":"r1-card-640.webp"}, ...]}}`.
Tutti i default anche come `server_default`; test dedicato per gli indici parziali.

## Moduli (in ordine)
1. Config: `MEDIA_ROOT` (controlli D-74), `MEDIA_MAX_PIXELS`, `MEDIA_QUOTA_MB`; `.env.example`; `tests/conftest.py`.
2. `pyproject.toml`: Pillow.
3. `app/models/media.py` (`Media`, `MediaFolder`, `MediaKind`) + `migrations/versions/0007_media.py`.
4. `app/services/media_types.py`: `sniff(data)` (puro, senza Pillow).
5. `app/services/media_images.py`: decodifica con limiti, normalizzazione, master, varianti, unica `save` su BytesIO.
6. `app/services/media_storage.py`: `new_key`, `put`, `path_for`, `discard`, `_root`.
7. `app/services/blocks.py`: `_media_ids` su `Mapping`/`Sequence`, `media_refs()`, `x-media: "image"|"file"` + meta-test.
8. `app/services/media_refs.py`: `document_refs`, `check_document`, `pages_using`.
9. `app/services/media.py`: upload, update, replace_file, delete_media, get_media, quota.
10. `app/services/media_library.py` (o `media_folders.py` se serve): elenco, serializzazione, URL pubblici, cartelle.
11. `publishing.py`: validazione + `check_document` in publish, schedule, publish-scheduled.
12. Renderer: `MediaView`, media della pagina con una query, `img`/`media_url`/`media_file`, OG, `app/static/cms/media.css`.
13. Tema `default`: `files.html` con `media_file()`, `hero` eager, `sizes`, CSS `object-fit`.
14. `app/public/media.py`: route D-75.
15. `app/api/admin/media.py` e `media_folders.py`; helper `upload_file()` in `app/api/validation.py`.
16. `app/cli_media.py`: `flask media-variants [--dry-run]`.
17. Guardiani: allowlist, `open`, route pubblica; togliere gli skip media in `test_template_lock.py` e da `SKIPPED_UNTIL_ROUTE`.
18. Docs: DECISIONI, ARCHITETTURA, TEMPLATE-CONTRACT, ROADMAP, HANDOFF.

## Route
| Metodo e path | Accesso | Risposte |
|---|---|---|
| GET `/api/admin/media` (`q`, `folder_id`, `kind`, `missing_alt`, `page`, `limit`) | `content.edit` | 200 · 422 |
| POST `/api/admin/media` (multipart `file`, `folder_id?`, `alt?`) | `content.edit` + CSRF | 201 · 200 doppione · 413 · 415 · 422 · 507 |
| GET `/api/admin/media/<id>` (con le pagine che lo usano) | `content.edit` | 200 · 404 |
| PATCH `/api/admin/media/<id>` (`version`, `name?`, `alt?`, `focal_x?`, `focal_y?`, `folder_id?`) | `content.edit` | 200 · 404 · 409 · 422 |
| POST `/api/admin/media/<id>/file` (sostituzione) | `content.edit` | 200 · 409 · 413 · 415 · 422 · 507 |
| DELETE `/api/admin/media/<id>` (`version`) | `content.edit` | 200 · 404 · 409 |
| GET/POST `/api/admin/media/folders`, PATCH/DELETE `/api/admin/media/folders/<id>` | `content.edit` | 200/201 · 404 · 409 · 422 |
| GET `/media/<key>/<filename>` | pubblico | 200 · 304 · 404 |
| CLI `flask media-variants` | Thias dopo un deploy | exit 0/1 |

## Rimandi da registrare in ROADMAP
- Fase 5: media picker, caricamento multiplo, punto focale con un clic, avvisi alt e doppioni, pagine che usano un media.
- Fase 6: impostazioni `media` (logo, favicon) e widget come fonti di "in uso" + `mark_changed`.
- Fase 7: alt per lingua; copertine delle collezioni come fonti di "in uso".
- Fase 8: Caddy che serve `/media` dal volume, backup di `MEDIA_ROOT`, pulizia file orfani, limite upload per utente, antivirus PDF.
- IDEE: HEIC/AVIF (pillow-heif), immagini decorative con `alt=""`, URL dei PDF col nome leggibile, anteprima prima pagina PDF, lightbox galleria.
