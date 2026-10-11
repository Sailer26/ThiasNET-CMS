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
- `layouts`: elenco layout selezionabili dall'utente e, per ciascuno, le **zone** con i blocchi ammessi e un eventuale `max`.
- `widget_areas`: aree globali (header, footer, sidebar) e tipi di widget ammessi.
- `menus`: posizioni dei menu e profondità massima.
- `collections`: tipi di contenuto con campi tipizzati.
- `image_sizes`: varianti da generare (larghezza, ratio).
- `settings`: le **uniche** personalizzazioni esposte al cliente. Tipi ammessi: `text`, `textarea`, `boolean`, `select` (opzioni fisse), `color` (hex, opzionalmente limitato a una `palette`), `media` (immagine dalla libreria), `url`. **Vietati**: campi CSS, JS, HTML o template liberi.

## Regole per chi scrive un tema
1. Ogni output di dati utente passa per autoescape; il rich text già sanitizzato si stampa con il filtro `|safe_html` (che ri-sanitizza), mai con `|safe`.
2. Colori dalle settings → solo come variabili CSS in un `<style>` generato dal CMS con valori validati.
3. Immagini sempre via helper `{{ img(media_id, size="card") }}` (srcset, width/height, lazy, alt).
4. Nessun JS inline; JS nei file `assets/`, compatibile con la CSP.
5. Un tema nuovo o modificato entra solo con commit + build + deploy.

## Cosa NON potrà mai fare un utente del pannello
Modificare/caricare file del tema, cambiare tema attivo (solo owner da file di config/env, non da UI), inserire CSS/JS/HTML arbitrario, inserire codice Jinja nei contenuti, aggiungere zone o layout non dichiarati.
