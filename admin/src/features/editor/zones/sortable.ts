// Trascinamento dentro una zona (D-109): regole pure e testi per i lettori di schermo.
import type { Announcements, ScreenReaderInstructions } from "@dnd-kit/core";

/** Posizione finale del blocco trascinato, o null se non si sposta. */
export function dropIndex(order: readonly string[], active: string, over: string | null): number | null {
  if (over === null || active === over) return null;
  const from = order.indexOf(active);
  const to = order.indexOf(over);
  return from < 0 || to < 0 ? null : to;
}

export const instructions: ScreenReaderInstructions = {
  draggable:
    "Per spostare il blocco premi spazio o invio, poi usa le frecce su e giù. " +
    "Premi di nuovo spazio o invio per lasciarlo, Esc per annullare.",
};

export function announcements(label: (id: string) => string, position: (id: string) => number): Announcements {
  const where = (id: string | number | undefined) => (id === undefined ? 0 : position(String(id)));
  return {
    onDragStart: ({ active }) => `Hai preso il blocco ${label(String(active.id))}.`,
    onDragOver: ({ active, over }) =>
      over ? `Il blocco ${label(String(active.id))} è sulla posizione ${where(over.id)}.` : undefined,
    onDragEnd: ({ active, over }) =>
      over
        ? `Blocco ${label(String(active.id))} lasciato nella posizione ${where(over.id)}.`
        : `Blocco ${label(String(active.id))} lasciato dov'era.`,
    onDragCancel: ({ active }) => `Spostamento del blocco ${label(String(active.id))} annullato.`,
  };
}
