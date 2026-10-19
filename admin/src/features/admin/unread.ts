// Numero dei messaggi da leggere nel menu (D-126): letto all'avvio, quando la finestra
// torna visibile e dopo ogni azione; mai con un timer (D-90).
import { useSyncExternalStore } from "react";
import { messagesSummary } from "../../api/admin";

let unread = 0;
const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function setUnread(value: number): void {
  unread = value;
  listeners.forEach((listener) => listener());
}

export async function refreshUnread(): Promise<void> {
  try {
    setUnread((await messagesSummary()).unread);
  } catch {
    // Il numero è un aiuto: se non arriva, il menu funziona lo stesso.
  }
}

export function useUnread(): number {
  return useSyncExternalStore(subscribe, () => unread);
}
