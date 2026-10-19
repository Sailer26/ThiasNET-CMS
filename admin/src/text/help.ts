// Testi dell'aiuto (5d): "Chiedi a Thias", tour.
export const hp = {
  menu: "Aiuto",
  retour: "Rifai il tour",
  ask: "Chiedi a Thias",
  askLabel: "Che cosa ti serve?",
  askHelp: "Scrivi con parole tue che cosa vuoi fare o che cosa non funziona. Thias ti risponde per email.",
  askPage: "Thias vedrà anche la pagina che hai aperto.",
  send: "Invia",
  sent: "Ricevuto: Thias ti risponde per email appena può.",
  maxLength: 2000,
  tour: {
    step: (n: number, total: number) => `Passo ${n} di ${total}`,
    back: "Indietro",
    next: "Avanti",
    done: "Fine",
    skip: "Salta il tour",
  },
  // D-133: cinque passi, frasi brevi. Il selettore indica cosa evidenziare (se c'è).
  steps: [
    {
      title: "Le pagine del sito",
      text: "Qui trovi tutte le pagine del sito, in ordine come nel menu. Le sottopagine stanno sotto la loro pagina.",
      target: '[data-tour="pages"]',
    },
    {
      title: "Apri una pagina",
      text: "Clicca il titolo di una pagina per modificarla. Accanto vedi se è online o se ha modifiche non pubblicate.",
      target: ".tree .row__title",
    },
    {
      title: "Modifica un blocco",
      text: "Nella pagina, clicca un blocco nell'elenco o nell'anteprima: il modulo si apre accanto. Le modifiche si salvano da sole e puoi annullarle.",
      target: null,
    },
    {
      title: "Anteprima e Pubblica",
      text: "A destra vedi la pagina come la vedranno i visitatori. Quando va bene premi Pubblica: prima controlliamo che non manchi niente.",
      target: null,
    },
    {
      title: "Serve aiuto?",
      text: "Nel menu Aiuto trovi \"Chiedi a Thias\" per scrivergli e puoi rifare questo giro quando vuoi.",
      target: '[data-tour="help"]',
    },
  ],
} as const;
