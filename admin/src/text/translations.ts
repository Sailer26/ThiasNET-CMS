// Testi delle traduzioni (7c, D-151, D-159).
export const tr = {
  title: "Traduzioni",
  intro: "Una traduzione parte come copia di questa pagina; da lì è una pagina a sé, con la sua pubblicazione.",
  loading: "Caricamento…",
  create: (language: string) => `Traduci in ${language}`,
  open: (language: string) => `Apri in ${language}`,
  status: { draft: "bozza", published: "online", scheduled: "programmata" } as Record<string, string>,
};
