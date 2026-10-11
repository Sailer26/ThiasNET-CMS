# Premortem — "È un anno dopo e ThiasNET CMS è fallito. Perché?"

| # | Causa probabile del fallimento | Segnale d'allarme | Contromisura |
|---|---|---|---|
| 1 | Scope esploso: si è costruito un mezzo WordPress e non si è mai consegnato un sito | Fase 5 iniziata prima che la 3 funzioni; feature "già che ci sono" | MVP chiuso nel PRD; primo cliente reale dopo Fase 6; ogni nuova idea va in `docs/IDEE.md`, non nel codice |
| 2 | Il lock del template aggirato (XSS nel rich text, SVG con script, Jinja nei contenuti, campo "colore" che accetta CSS) | Bug report "il sito si vede strano"; test di sicurezza saltati | Test `test_template_lock.py` obbligatori in CI; nh3; niente SVG; settings tipizzate; tema `:ro` nel container |
| 3 | Il cliente si sente ingabbiato ("voglio solo spostare quel bottone") e ti chiama per ogni cosa | Molte richieste di micro-modifiche grafiche | Temi con blocchi e varianti ben pensati; settings sensate (palette, stile header); listino per modifiche tema |
| 4 | Manutenzione insostenibile su N istanze (aggiornamenti, sicurezza, backup) | Istanze su versioni diverse; backup mai provati | Un'immagine Docker unica versionata; script di update per tutte le istanze; test di restore mensile |
| 5 | Codice generato da Claude incoerente tra fasi (duplicazioni, logica nelle route) | File enormi, test che non coprono | CLAUDE.md + una fase per sessione + `/code-review` prima di chiudere; agent `security-reviewer` |
| 6 | Editor admin troppo complesso per l'utente non tecnico | Clienti che non lo usano | Test con un cliente vero a fine Fase 5; meno opzioni, default buoni |
| 7 | Migrazioni DB rotte in produzione | Errori al deploy | Alembic sempre; backup automatico prima di ogni migrazione |
| 8 | Concorrenza con WordPress/Webflow sul prezzo | Clienti che chiedono "perché non WordPress?" | Vendere: sicurezza, niente plugin da aggiornare, hosting svizzero, assistenza locale, sito che non si rompe |

**Decisione da prendere prima di partire:** un'istanza per cliente (scelta attuale, più semplice e isolata) o multi-tenant? Se prevedi > 15–20 clienti in 2 anni, rivaluta dopo la Fase 8.
