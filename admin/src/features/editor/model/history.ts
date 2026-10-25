// Annulla/ripristina (D-105): una sola storia, 100 passi, battute nello stesso campo unite.
// Generica: la usano le pagine e le notizie (7b).
import type { PageDocument } from "./document";

export const HISTORY_LIMIT = 100;
export const MERGE_MS = 1000;

export interface History<D = PageDocument> {
  past: D[];
  present: D;
  future: D[];
  lastKey: string | null;
  lastAt: number;
}

export function startHistory<D>(doc: D): History<D> {
  return { past: [], present: doc, future: [], lastKey: null, lastAt: 0 };
}

/** Nuovo stato. `key` (es. "uid:campo") unisce le battute vicine nello stesso campo. */
export function commit<D>(history: History<D>, doc: D, key: string | null, now: number): History<D> {
  if (doc === history.present) return history;
  const merge = key !== null && key === history.lastKey && now - history.lastAt <= MERGE_MS;
  const past = merge ? history.past : [...history.past, history.present].slice(-HISTORY_LIMIT);
  return { past, present: doc, future: [], lastKey: key, lastAt: now };
}

export function undo<D>(history: History<D>): History<D> {
  const previous = history.past.at(-1);
  if (previous === undefined) return history;
  return {
    past: history.past.slice(0, -1),
    present: previous,
    future: [history.present, ...history.future],
    lastKey: null,
    lastAt: 0,
  };
}

export function redo<D>(history: History<D>): History<D> {
  if (history.future.length === 0) return history;
  const [next, ...future] = history.future as [D, ...D[]];
  return { past: [...history.past, history.present], present: next, future, lastKey: null, lastAt: 0 };
}
