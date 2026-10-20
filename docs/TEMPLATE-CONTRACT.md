# Template Contract — come un tema parla al CMS

Il tema è codice di Thias. Il CMS lo **legge**, non lo scrive mai. Tutto ciò che il cliente può toccare è dichiarato qui, in `theme.json`.

## Struttura di un tema
```
themes/<nome>/
  theme.json          # contratto (validato all'avvio; se invalido l'app non parte)
  layouts/            # page.html, home.html, entry.html, 404.html ...
  partials/           # header.html, footer.html, menu.html ...
  blocks/             # un file per tipo di blocco: text.html, image.html ...
  widgets/            # un file per tipo di widget
  assets/             # css, js, font, immagini del tema (servite con hash + cache lunga)
```

## theme.json — cosa dichiara
- `layouts`: elenco layout selezionabili dall'utente e, per ciascuno, le **zone** con `label` (il nome che il cliente vede nell'editor, es. "Contenuto principale"; senza, vede il nome tecnico), i blocchi ammessi e un eventuale `max`. Una pagina nuova nasce col layout `page` (la homepage con `home`), se il tema li ha (D-95).
- `widget_areas`: aree globali (header, footer, sidebar) e tipi di widget ammessi.
- `menus`: posizioni dei menu e profondità massima.
- `collections`: tipi di contenuto con campi tipizzati.
- `image_sizes`: varianti da generare (larghezza, ratio).
- `block_variants` (D-03): per ogni tipo di blocco, le varianti grafiche che il cliente può scegliere. Ogni variante ha `label` (italiano), `thumbnail` (immagine in `assets/variants/`) ed è un valore di un enum chiuso: il server rifiuta varianti non dichiarate. Il template del blocco riceve `block.variant` e lo usa solo come classe/ramo del template, mai come CSS o markup. Esempio:
  ```json
  "block_variants": {
    "text_image": {
      "default": "image_left",
      "options": {
        "image_left":  { "label": "Immagine a sinistra", "thumbnail": "variants/text_image-left.webp" },
        "image_right": { "label": "Immagine a destra",   "thumbnail": "variants/text_image-right.webp" },
        "dark":        { "label": "Sfondo scuro",        "thumbnail": "variants/text_image-dark.webp" }
      }
    }
  }
  ```

## Template unici per ogni sito (D-04)
Tutti i temi condividono gli **stessi tipi di blocco e widget** (schema dati e editor nel core), ma ogni tema è libero su tutto il resto: markup dei blocchi, layout, tipografia, CSS, animazioni (in file `assets/`), varianti. Un tema nuovo nasce copiando la struttura di `default` e riscrivendo la grafica da zero, senza toccare `app/` o `admin/`. Il contratto (questo documento + lo schema di `theme.json`) è l'unico punto di contatto: se un tema ha bisogno di un dato che i blocchi non hanno, è una modifica al core da decidere a parte.
- `settings`: le **uniche** personalizzazioni esposte al cliente. Tipi ammessi: `text`, `textarea`, `boolean`, `select` (opzioni fisse), `color` (hex, opzionalmente limitato a una `palette`), `media` (immagine dalla libreria), `url`. **Vietati**: campi CSS, JS, HTML o template liberi.

## Regole per chi scrive un tema
1. Ogni output di dati utente passa per autoescape; il rich text già sanitizzato si stampa con il filtro `|safe_html` (che ri-sanitizza), mai con `|safe`.
2. Colori dalle settings → solo come variabili CSS nel file `/_vars.css` generato dal CMS con valori validati (D-59), es. `--accent-color`. Nessun `<style>` o `style=` nei template.
3. Immagini sempre via helper `{{ img(media_id, size="card") }}` (srcset, width/height, lazy, alt); mai `<img src=...>` scritto a mano con `media_url()`.
4. Nessun JS inline; JS nei file `assets/`, compatibile con la CSP.
5. Un tema nuovo o modificato entra solo con commit + build + deploy.
6. Ogni blocco nel template ha l'attributo `data-block-id="{{ block.id }}"` sull'elemento radice: serve all'anteprima live per evidenziare e selezionare il blocco (D-02). In modalità pubblica l'attributo è innocuo.
7. Il tema fornisce lo stile del banner cookie e dei segnaposto "clicca per caricare" (video/mappe), ma il comportamento è del CMS (D-06).

## Template obbligatori (controllati da `theme-check`, D-63)
- `layouts/<layout>.html` per ogni layout dichiarato e `layouts/404.html`;
- `blocks/<tipo>.html` per ogni tipo ammesso in almeno una zona;
- `partials/contact_form.html` se il blocco `contacts` è ammesso;
- in qualche template devono comparire `{{ cms_head() }}` (nel `<head>`) e `{{ cms_body_end() }}` (prima di `</body>`).
I template sono eseguiti in sandbox (D-52): non possono leggere file fuori dal tema né raggiungere Python.

## Cosa ricevono i template (D-56)
| Nome | Contenuto |
|---|---|
| `page` | `title`, `locale`, `layout`, `path`, `seo`, `is_home`, `noindex`, `zones` |
| `site` | `name`, `base_url`, `locale` (lingua principale), `year`, `logo` (id per `img()`, o `None`), `email`, `phone`, `address`, `social` (coppie `(rete, url)`): dal pannello, D-143 |
| `settings` | impostazioni del tema: i valori scelti nel pannello, validati contro `theme.json > settings`; un valore non più valido vale il `default` |
| `breadcrumbs` | elenco di `{title, url, current}` |
| `preview` | `true` dentro l'anteprima del pannello |
| `cms_head()` · `cms_body_end()` | `<title>`, description, canonical, robots, `/_vars.css` · banner del consenso e script del CMS |
| `render_zone(nome)` · `zone_has_blocks(nome)` | blocchi di una zona già renderizzati · se la zona ha blocchi |
| `menu("posizione")` | voci `{title, url, current, children}` per ogni menu dichiarato in `theme.json > menus` (D-145); `children` fino a `max_depth`. "main" è automatico (D-58) finché il cliente non lo cambia; gli altri sono vuoti finché non li riempie |
| `img(media_id, size="card", sizes=None, eager=False, css_class=None)` | `<img>` responsive (D-81): `srcset` con larghezza normale e doppia, `width`/`height`, `alt`, `loading="lazy"` (con `eager=True` per l'immagine in cima, es. hero). `size` deve essere un `image_sizes` del tema (altrimenti errore del tema). `sizes` e `css_class` accettano solo testo semplice. Media mancante: niente sul sito, segnaposto in anteprima |
| `media_url(id)` | indirizzo del file principale, o `None` |
| `media_file(id)` | per i file da scaricare: `{url, name, ext, size_label}` (es. `PDF`, `340 kB`), o `None` |
| `asset("css/site.css")` | indirizzo versionato di un file in `assets/` |
| `embed(block)` | dati del segnaposto di video e mappe: `kind`, `src`, `link`, `title`, `provider` |
| `contact_form(block)` | stato del modulo: `action`, `token`, `values`, `errors`, `sent`, `disabled` |
| `cms_text("chiave")` | testi del CMS nella lingua della pagina (consenso, modulo, 404…) |
| filtri `safe_html` · `clean_url` | rich text ripulito · link solo se sicuro, altrimenti vuoto |

Nel template di un blocco: `block.id` (va in `data-block-id`), `block.type`, `block.variant`, `block.data`.
Per i campi che hanno il nome di un metodo dei dizionari (`items`) usare `block.data.get("items")`.

## Markup che il CMS si aspetta
- **Video e mappe** (D-60): un contenitore con `data-cms-embed="video|map"`, `data-cms-embed-src`, `data-cms-embed-title`, un pulsante `.cms-embed__load` e un link esterno. `consent.js` crea l'iframe solo verso YouTube (nocookie), Vimeo e OpenStreetMap.
- **Consenso**: il banner lo produce `cms_body_end()` (classi `.cms-consent*`); il tema lo stila e mette nel piè di pagina un pulsante con `data-cms-consent-open` per riaprirlo.
- **Modulo contatti** (D-61): `method="post"`, `action="{{ form.action }}"`, campi `token` (nascosto), `name`, `email`, `phone`, `message` e il campo trappola `website` nascosto agli utenti (non `type="hidden"`); id del modulo `contatti-{{ block.id }}`.
- **Anteprima**: la classe `.cms-preview-active` evidenzia il blocco selezionato; `.cms-media-placeholder` è il segnaposto delle immagini.
- **Immagini** (D-80): `img()` mette le classi `cms-img cms-fx-N cms-fy-N` (N = 0…10, il punto focale) e il CMS carica `/static/cms/media.css`, che traduce le classi in `object-position`. Il tema decide la forma del riquadro (es. `object-fit: cover` e `aspect-ratio`): così il ritaglio segue il punto focale scelto dal cliente.
- **Social**: `cms_head()` aggiunge Open Graph e Twitter con indirizzi assoluti da `SITE_URL`; l'immagine è quella scelta nella SEO della pagina o la prima del contenuto, nella variante `_og` (1200×630).

## Formati delle immagini (`image_sizes`)
Ogni voce ha `width` (pixel) e, se serve, `ratio` (es. `"16:9"`): il CMS crea due varianti WebP (normale e doppia) ritagliate attorno al punto focale. Le chiavi che iniziano con `_` sono riservate al CMS (`_panel` per le miniature del pannello, `_og` per i social). Dopo un deploy che cambia `image_sizes`, Thias lancia `flask media-variants` (con `--dry-run` per vedere quante immagini cambiano): fino ad allora `img()` usa il file principale, mai un buco.

## Cosa NON potrà mai fare un utente del pannello
Modificare/caricare file del tema, cambiare tema attivo (solo owner da file di config/env, non da UI), inserire CSS/JS/HTML arbitrario, inserire codice Jinja nei contenuti, aggiungere zone o layout non dichiarati.
