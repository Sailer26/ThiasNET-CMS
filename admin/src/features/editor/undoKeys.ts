// Annulla e ripristina da tastiera (D-105), anche dentro i campi; mai dentro una finestra.
import type { KeyboardEvent } from "react";

export function undoKeys(onUndo: () => void, onRedo: () => void) {
  return (event: KeyboardEvent) => {
    const mod = event.ctrlKey || event.metaKey;
    if (!mod || (event.target instanceof Element && event.target.closest("dialog"))) return;
    const key = event.key.toLowerCase();
    if (key === "z" && !event.shiftKey) {
      event.preventDefault();
      onUndo();
    } else if (key === "y" || (key === "z" && event.shiftKey)) {
      event.preventDefault();
      onRedo();
    }
  };
}
