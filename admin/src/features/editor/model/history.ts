// Annulla/ripristina (D-105): una sola storia, 100 passi, battute nello stesso campo unite.
import type { PageDocument } from "./document";

export const HISTORY_LIMIT = 100;
export const MERGE_MS = 1000;

export interface History {
  past: PageDocument[];
  present: PageDocument;
  future: PageDocument[];
  lastKey: string | null;
  lastAt: number;
}

export function startHistory(doc: PageDocument): History {
  return { past: [], present: doc, future: [], lastKey: null, lastAt: 0 };
}

/** Nuovo stato. `key` (es. "uid:campo") unisce le battute vicine nello stesso campo. */
export function commit(history: History, doc: PageDocument, key: string | null, now: number): History {
  if (doc === history.present) return history;
  const merge = key !== null && key === history.lastKey && now - history.lastAt <= MERGE_MS;
  const past = merge ? history.past : [...history.past, history.present].slice(-HISTORY_LIMIT);
  return { past, present: doc, future: [], lastKey: key, lastAt: now };
}

export function undo(history: History): History {
  const previous = history.past.at(-1);
  if (!previous) return history;
  return {
    past: history.past.slice(0, -1),
    present: previous,
    future: [history.present, ...history.future],
    lastKey: null,
    lastAt: 0,
  };
}

export function redo(history: History): History {
  const [next, ...future] = history.future;
  if (!next) return history;
  return { past: [...history.past, history.present], present: next, future, lastKey: null, lastAt: 0 };
}
