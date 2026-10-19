// Etichette italiane delle azioni del registro (D-124); un codice sconosciuto resta com'è.
const LABELS: Record<string, string> = {
  "auth.login": "Accesso",
  "auth.logout": "Uscita",
  "auth.logout_all": "Uscita da tutti i dispositivi",
  "auth.password_changed": "Password cambiata",
  "auth.login_failed": "Accesso non riuscito",
  "auth.password_change_failed": "Cambio password non riuscito",
  "auth.password_reset_cli": "Password reimpostata da ThiasNET",
  "auth.totp_failed": "Codice a 6 cifre sbagliato",
  "totp.enabled": "Codice a 6 cifre attivato",
  "totp.disabled": "Codice a 6 cifre disattivato",
  "totp.reset": "Codice a 6 cifre azzerato",
  "totp.reset_cli": "Codice a 6 cifre azzerato da ThiasNET",
  "totp.enable_failed": "Attivazione del codice non riuscita",
  "totp.disable_failed": "Disattivazione del codice non riuscita",
  "user.created": "Utente creato",
  "user.updated": "Utente modificato",
  "page.created": "Pagina creata",
  "page.slug_changed": "Indirizzo della pagina cambiato",
  "page.draft_started": "Modifiche iniziate",
  "page.moved": "Pagina spostata",
  "page.reordered": "Ordine delle pagine cambiato",
  "page.published": "Pagina pubblicata",
  "page.unpublished": "Pagina ritirata",
  "page.scheduled": "Pubblicazione programmata",
  "page.unscheduled": "Programmazione annullata",
  "page.schedule_failed": "Programmazione non riuscita",
  "page.trashed": "Pagina nel cestino",
  "page.restored": "Pagina recuperata",
  "page.draft_discarded": "Modifiche scartate",
  "page.revision_restored": "Versione ripristinata",
  "media.uploaded": "File caricato",
  "media.updated": "File modificato",
  "media.file_replaced": "File sostituito",
  "media.deleted": "File eliminato",
  "media.variants_refreshed": "Varianti aggiornate",
  "media_folder.created": "Cartella creata",
  "media_folder.renamed": "Cartella rinominata",
  "media_folder.moved": "Cartella spostata",
  "media_folder.deleted": "Cartella eliminata",
  "contact_message.deleted": "Messaggio eliminato",
};

export function actionLabel(action: string): string {
  return LABELS[action] ?? action;
}

export const CATEGORY_LABELS: Record<string, string> = {
  pages: "Pagine",
  media: "Media",
  users: "Utenti",
  access: "Accessi",
  totp: "Codice a 6 cifre",
  messages: "Messaggi",
};

function plain(value: unknown): string {
  return typeof value === "object" && value !== null ? JSON.stringify(value) : String(value);
}

/** Dettagli come testo semplice ("chiave: prima → dopo"), mai HTML. */
export function diffLines(diff: Record<string, unknown> | null): string[] {
  if (!diff) return [];
  return Object.entries(diff).map(([key, value]) => {
    if (Array.isArray(value) && value.length === 2) return `${key}: ${plain(value[0])} → ${plain(value[1])}`;
    return `${key}: ${plain(value)}`;
  });
}
