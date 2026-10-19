# Test d'uso con un cliente vero (PREMORTEM #6)

Lo esegue Thias con **una persona che non ha mai visto il pannello** (meglio se è chi poi aggiornerà il sito:
segretaria del comune, titolare di una PMI, volontario di un'associazione). Durata: 45–60 minuti.
Il criterio in `docs/ROADMAP.md` ("Test d'uso con un cliente vero") si spunta solo dopo averlo fatto.

## Prima del test
- Sito di prova con contenuti realistici: homepage, 5–6 pagine (una con sottopagine), un modulo contatti,
  10–15 foto nella libreria (almeno una **senza testo alternativo**), un PDF.
- Una pagina con un **link interno rotto** (verso una pagina nel cestino) e senza descrizione per Google.
- Un utente **editor con "Può pubblicare"** appena creato: al primo accesso deve partire il tour.
- `SUPPORT_EMAIL` impostato su un indirizzo che Thias legge durante il test.
- Un PC (o portatile) e un telefono della persona, se lo usa per il lavoro.
- Registrare lo schermo e la voce (con il permesso scritto della persona) oppure prendere appunti.

## Come condurlo
- Dire all'inizio: "Stiamo provando il programma, non te. Se qualcosa non riesci, è colpa del programma."
- Chiedere di **pensare ad alta voce**. Non aiutare: se la persona è bloccata da più di 2 minuti, prendere
  nota e dare il minimo indizio ("dove cercheresti?"), poi segnare "con aiuto".
- Non spiegare il pannello prima: il tour e i suggerimenti devono bastare.

## Compiti (in quest'ordine)
| # | Compito detto alla persona | Cosa osservare |
|---|----------------------------|----------------|
| 1 | "Entra nel pannello con l'email e la password che ti ho dato." | Il tour parte? Lo legge o lo salta? Capisce dove sono le pagine? |
| 2 | "Nella pagina *Orari*, cambia l'orario del venerdì." | Trova la pagina; capisce che salva da sola (scritta in alto); usa l'anteprima. |
| 3 | "Nella pagina *Chi siamo*, metti un'altra foto al posto di quella che c'è." | Apre la libreria; carica o sceglie; aggiunge il testo alternativo quando glielo chiede. |
| 4 | "Aggiungi in fondo alla pagina *Eventi* un pulsante che porta alla pagina *Contatti*." | Trova "Aggiungi blocco", sceglie "Invito all'azione", scrive il link. |
| 5 | "Pubblica la pagina *Eventi*." | Legge gli avvisi (descrizione per Google, link rotto)? Usa "Vai al campo" o "Pubblica comunque"? |
| 6 | "Hai sbagliato: rimetti la pagina *Chi siamo* com'era ieri." | Trova "Versioni", guarda, ripristina. |
| 7 | "Non riesci a fare una cosa: chiedi aiuto a Thias da dentro il pannello." | Trova il menu Aiuto e "Chiedi a Thias"; il messaggio arriva con la pagina giusta. |
| 8 | (sul telefono) "Hai finito la modifica dal computer ieri sera: pubblicala dal telefono." | Trova "Pubblica le modifiche"; capisce il messaggio se c'è un errore da correggere. |

## Per ogni compito annotare
- Riuscito: **sì / con aiuto / no**
- Tempo (minuti)
- Dove si è bloccata o ha esitato, parole testuali dette ad alta voce
- Errori (click sbagliati, cose cercate nel posto sbagliato)

## Domande finali (5 minuti)
1. Da 1 a 5, quanto è stato facile? Perché?
2. Cosa ti ha confuso di più?
3. C'è qualcosa che ti aspettavi e non hai trovato?
4. Il giro iniziale (tour) è servito? Troppo lungo, troppo corto?
5. Useresti il telefono per pubblicare? Per fare cos'altro?

## Cosa decidere dopo (elementi condizionali di D-132)
| Se si osserva… | Allora… |
|----------------|---------|
| Sul tablet le azioni delle righe dell'albero confondono o non si trovano | Menu "⋯" per le azioni delle righe (rimando della 5a) |
| L'anteprima mostra il banner dei cookie e disturba | Nascondere il banner nell'anteprima del pannello (rimando della 5b-1) |
| Attivare il codice a 6 cifre copiando la chiave è difficile | QR code per il codice a 6 cifre (IDEE) |
| Il tour viene saltato subito o non ricordato | Rivedere testi e numero dei passi (D-133) |
| Gli avvisi prima di pubblicare vengono ignorati | Rivedere testi o rendere bloccanti alcuni avvisi (D-135) |

Annotare le decisioni prese in `docs/DECISIONI.md` e i rimandi in `docs/ROADMAP.md`.
