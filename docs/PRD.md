# PRD — ThiasNET CMS

> Le decisioni prese dopo il kit iniziale sono in `docs/DECISIONI.md` (D-xx) e prevalgono su questo documento in caso di dubbio.

## Obiettivo
Un CMS leggero e proprietario con cui ThiasNET consegna siti ai clienti. Il cliente gestisce i contenuti in autonomia; la grafica (template) resta sotto controllo esclusivo di Thias, così il sito non si "rompe" e resta coerente.

**Priorità n. 1: facilità d'uso** per un cliente non tecnico. **Priorità n. 2: ogni sito ha una grafica unica** — tutti i temi partono dagli stessi blocchi e widget, ma markup, stile e varianti sono propri di ciascun tema (D-04).

## Utenti e ruoli
| Ruolo | Chi | Può |
|---|---|---|
| owner | Thias | tutto ciò che fa admin + gestione utenti, impostazioni di sistema, backup, log. **Non** modifica il tema dal pannello (solo via git). |
| admin | referente del cliente | pagine, contenuti, media, widget, menu, impostazioni del tema esposte, utenti editor |
| editor | collaboratori del cliente | creare/modificare contenuti e media; pubblicazione solo se abilitata da admin (`can_publish`, D-15) |

## Funzionalità (MVP)
1. **Pagine**: albero gerarchico, slug, bozza/pubblicata/programmata (job periodico, D-16), anteprima, revisioni con ripristino, SEO (title, description, immagine OG, noindex).
2. **Blocchi**: il contenuto di una pagina è una lista di blocchi per ogni zona del layout (es. `main`, `sidebar`). 13 blocchi base: hero, titolo, testo ricco, immagine, galleria, testo+immagine, pulsante/CTA, citazione, video (YouTube/Vimeo via embed sicuro, clicca-per-caricare), separatore, mappa (clicca-per-caricare), lista file scaricabili, contatti (con modulo opzionale). Il tema decide quali blocchi sono ammessi in quale zona e quali **varianti** offre per ciascun blocco (D-03).
3. **Collezioni**: tipi di contenuto ripetibili dichiarati dal tema (es. news, eventi, team) con campi definiti, listing e pagina di dettaglio.
4. **Media library**: upload immagini e PDF, cartelle, alt text obbligatorio, ritaglio punto focale, varianti responsive WebP generate automaticamente, ricerca, rilevamento duplicati.
5. **Widget**: elementi riutilizzabili e globali (orari, contatti, banner avviso, ultimi articoli, social) posizionabili nelle zone globali del tema (header, footer, sidebar) con ordine e visibilità per pagina.
6. **Menu**: per ogni posizione dichiarata dal tema; voci verso pagine, collezioni o URL esterni; drag&drop.
7. **Impostazioni sito**: nome, logo, contatti, social, favicon, analytics (solo ID, non script libero) + i soli campi esposti dal tema.
8. **SEO tecnico**: sitemap.xml, robots.txt, redirect 301 gestiti, URL canonici, dati strutturati base.
9. **Multilingua**: pagine collegate tra lingue (it/de/rm/en), selettore lingua nel tema.
10. **Sicurezza e manutenzione**: audit log, backup DB+media scaricabile dall'owner, rate limiting login, TOTP.
11. **Editor con anteprima live** (D-02): form a sinistra, sito reale del tema a destra aggiornato in tempo reale; click su un blocco nell'anteprima apre il suo form. Salvataggio automatico delle bozze e annulla/ripristina (D-07).
12. **Modulo contatti** (D-05): invio email via SMTP, antispam senza servizi Google (honeypot, rate limit, tempo minimo), messaggi salvati anche nel pannello.
13. **Consenso cookie** (D-06): banner del CMS (stile dal tema), contenuti esterni e analytics caricati solo dopo consenso.
14. **Aiuto in-app** (D-08, D-09): tour guidato al primo accesso, suggerimenti accanto ai campi, controllo prima di pubblicare, bottone "Chiedi a Thias".

## Esperienza d'uso (principi)
- Linguaggio semplice, niente gergo tecnico; ogni campo ha un suggerimento.
- Default buoni: una pagina nuova è già pubblicabile e bella con il tema.
- Nessuna azione distruttiva senza conferma; tutto ripristinabile (revisioni, annulla).
- Pannello per PC e tablet; da telefono solo azioni rapide (D-10).

## Fuori scope MVP
E-commerce, area membri, page builder libero, editor di temi, plugin di terze parti, multi-sito nella stessa istanza (valutare in fase successiva), assistente AI (D-13, vedi `docs/IDEE.md`).

## Requisiti non funzionali
- Pagina pubblica < 200 ms da cache, Lighthouse ≥ 90 sul tema default.
- Accessibilità: tema default WCAG 2.1 AA; alt text obbligatorio.
- nLPD (CH) / GDPR: niente tracciamento senza consenso, dati e backup su hosting svizzero/UE.
- Un'istanza per cliente, deploy in Docker.
