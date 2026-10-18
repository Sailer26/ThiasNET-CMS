// Riassunto di un blocco nella lista: il primo testo utile, senza tag.
import type { BlockDoc } from "../model/document";

const MAX = 60;
const TEXT_FIELDS = ["title", "text", "body", "label", "button_label", "caption", "address"];

function plain(value: string): string {
  const doc = new DOMParser().parseFromString(value, "text/html"); // mai inserito nella pagina
  return (doc.body.textContent ?? "").replace(/\s+/g, " ").trim();
}

export function summary(block: BlockDoc): string {
  for (const field of TEXT_FIELDS) {
    const value = block.data[field];
    if (typeof value === "string" && value.trim()) {
      const text = plain(value);
      return text.length > MAX ? `${text.slice(0, MAX - 1)}…` : text;
    }
  }
  const items = block.data.items;
  return Array.isArray(items) && items.length ? `${items.length}` : "";
}
