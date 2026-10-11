# PRD — ThiasCMS

## Obiettivo
Un CMS leggero e proprietario con cui ThiasNET consegna siti ai clienti. Il cliente gestisce i contenuti in autonomia; la grafica (template) resta sotto controllo esclusivo di Thias, così il sito non si "rompe" e resta coerente.

## Utenti e ruoli
| Ruolo | Chi | Può |
|---|---|---|
| owner | Thias | tutto ciò che fa admin + gestione utenti, impostazioni di sistema, backup, log. **Non** modifica il tema dal pannello (solo via git). |
| admin | referente del cliente | pagine, contenuti, media, widget, menu, impostazioni del tema esposte, utenti editor |
| editor | collaboratori del cliente | creare/modificare contenuti e media; pubblicazione solo se abilitata da admin |

## Funzionalità (MVP)
1. **Pagine**: albero gerarchico, slug, bozza/pubblicata/programmata, anteprima, revisioni con ripristino, SEO (title, description, immagine OG, noindex).
2. **Blocchi**: il contenuto di una pagina è una lista di blocchi per ogni zona del layout (es. `main`, `sidebar`). Blocchi base: titolo, testo ricco, immagine, galleria, testo+immagine, pulsante/CTA, citazione, video (YouTube/Vimeo via embed sicuro), separatore, mappa, lista file scaricabili, contatti. Il tema decide quali blocchi sono ammessi in quale zona.
3. **Collezioni**: tipi di contenuto ripetibili dichiarati dal tema (es. news, eventi, team) con campi definiti, listing e pagina di dettaglio.
4. **Media library**: upload immagini e PDF, cartelle, alt text obbligatorio, ritaglio punto focale, varianti responsive WebP generate automaticamente, ricerca, rilevamento duplicati.
5. **Widget**: elementi riutilizzabili e globali (orari, contatti, banner avviso, ultimi articoli, social) posizionabili nelle zone globali del tema (header, footer, sidebar) con ordine e visibilità per pagina.
6. **Menu**: per ogni posizione dichiarata dal tema; voci verso pagine, collezioni o URL esterni; drag&drop.
7. **Impostazioni sito**: nome, logo, contatti, social, favicon, analytics (solo ID, non script libero) + i soli campi esposti dal tema.
8. **SEO tecnico**: sitemap.xml, robots.txt, redirect 301 gestiti, URL canonici, dati strutturati base.
9. **Multilingua**: pagine collegate tra lingue (it/de/rm/en), selettore lingua nel tema.
10. **Sicurezza e manutenzione**: audit log, backup DB+media scaricabile dall'owner, rate limiting login, TOTP.

## Fuori scope MVP
E-commerce, area membri, page builder libero, editor di temi, plugin di terze parti, multi-sito nella stessa istanza (valutare in fase successiva).

## Requisiti non funzionali
- Pagina pubblica < 200 ms da cache, Lighthouse ≥ 90 sul tema default.
- Accessibilità: tema default WCAG 2.1 AA; alt text obbligatorio.
- nLPD (CH) / GDPR: niente tracciamento senza consenso, dati e backup su hosting svizzero/UE.
- Un'istanza per cliente, deploy in Docker.
