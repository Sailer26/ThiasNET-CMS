# Decisioni — ThiasNET CMS

Registro delle decisioni di prodotto. Ogni decisione ha un ID stabile (D-xx): se cambia, si aggiunge una nuova riga che la sostituisce, non si cancella quella vecchia.

| ID | Data | Decisione | Motivo |
|---|---|---|---|
| D-01 | 2026-10-11 | Il prodotto si chiama **ThiasNET CMS** (sostituisce "ThiasNET CMS" del kit). | Coerenza con il marchio ThiasNET. |
| D-02 | 2026-10-11 | Editor pagina con **anteprima live affiancata**: a sinistra lista blocchi e form, a destra il sito reale renderizzato dal tema attivo (iframe) che si aggiorna mentre si scrive. Click su un blocco nell'anteprima apre il suo form. | Massima facilità d'uso senza dare al cliente controllo sul tema. |
| D-03 | 2026-10-11 | **Varianti di blocco** dichiarate dal tema in `theme.json` (es. `dark`, `image_right`, `card`). Il cliente le sceglie da miniature visive; i valori sono enum chiusi validati dal server. | Riduce le richieste di micro-modifiche grafiche (PREMORTEM #3) e permette temi davvero diversi tra loro. |
| D-04 | 2026-10-11 | Ogni tema cliente può avere una grafica **totalmente diversa** dagli altri partendo dallo stesso set di blocchi/widget: il core definisce dati e comportamento, il tema definisce markup, CSS, varianti e miniature. Comando futuro: "creami un template per il mio CMS" → nuovo `themes/<cliente>/` creato con l'agent `theme-builder`. | Requisito di prodotto di Thias. |
| D-05 | 2026-10-11 | **Modulo contatti** con invio email nell'MVP: antispam con honeypot + rate limit + tempo minimo di compilazione, niente reCAPTCHA/servizi Google. Destinatario configurabile dall'admin, invio via SMTP da `.env`. | Richiesto da quasi tutti i clienti; nLPD. |
| D-06 | 2026-10-11 | **Banner consenso cookie** nell'MVP. Video (YouTube/Vimeo) e mappe sono "clicca per caricare" finché non c'è consenso; YouTube via `youtube-nocookie.com`. Analytics caricati solo dopo consenso. | nLPD/GDPR. |
| D-07 | 2026-10-11 | **Salvataggio automatico** delle bozze nell'editor + **annulla/ripristina** (Ctrl+Z / Ctrl+Y). L'autosave non pubblica mai. | Il cliente non perde lavoro. |
| D-08 | 2026-10-11 | **Tour guidato** al primo accesso (saltabile, riavviabile dal menu Aiuto). | Onboarding del cliente non tecnico. |
| D-09 | 2026-10-11 | Aiuto in-app: **suggerimenti accanto ai campi** in italiano semplice; **controllo prima di pubblicare** (alt mancanti, SEO mancante, link interni rotti, pagina vuota) che avvisa ma non blocca, tranne alt mancanti che bloccano; bottone **"Chiedi a Thias"** che invia una richiesta con pagina corrente e descrizione. | Riduce chiamate di assistenza. |
| D-10 | 2026-10-11 | Pannello pensato per **PC e tablet**; da telefono solo azioni rapide (banner avviso, notizia, pubblicazione). | Uso reale dei clienti. |
| D-11 | 2026-10-11 | `hero` è il **13° blocco base**. | Era usato in `theme.json` ma assente dal PRD. |
| D-12 | 2026-10-11 | Il **romancio (rm)** è attivo nel tema default insieme a it/de/en. | Clienti nei Grigioni. |
| D-13 | 2026-10-11 | **Assistente AI** (testi, traduzioni) fuori dall'MVP: annotato in `docs/IDEE.md`; il pannello va progettato in modo che sia aggiungibile in seguito. | Contenere lo scope (PREMORTEM #1). |
| D-14 | 2026-10-11 | Le impostazioni del tema si salvano su `PUT /api/admin/settings/appearance` (non `/settings/theme`). | Evita il conflitto con `test_no_admin_route_touches_theme_files`, che vieta route admin mutanti contenenti "theme". |
| D-15 | 2026-10-11 | Pubblicazione per editor controllata dal flag `users.can_publish` (impostato da admin/owner). | Mancava nel modello dati. |
| D-16 | 2026-10-11 | Pubblicazione programmata eseguita da un job periodico (comando `flask publish-scheduled` lanciato ogni minuto) + controllo al momento della richiesta per sicurezza. | Mancava il meccanismo. |
