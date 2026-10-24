// Operazioni pure sulla lista dei widget di un'area (6c): ogni funzione restituisce una lista nuova.
import type { WidgetItem, WidgetType } from "../../api/widgets";
import { newUid } from "../menus/tree";

export const NOTICE = "notice";

export function moveBy(items: WidgetItem[], uid: string, delta: -1 | 1): WidgetItem[] {
  const from = items.findIndex((item) => item.uid === uid);
  const to = from + delta;
  if (from < 0 || to < 0 || to >= items.length) return items;
  const next = [...items];
  [next[from], next[to]] = [next[to]!, next[from]!];
  return next;
}

export function removeWidget(items: WidgetItem[], uid: string): WidgetItem[] {
  return items.filter((item) => item.uid !== uid);
}

export function replaceWidget(items: WidgetItem[], next: WidgetItem): WidgetItem[] {
  return items.some((item) => item.uid === next.uid) ? items.map((item) => (item.uid === next.uid ? next : item)) : [...items, next];
}

/** Il widget vicino da mettere a fuoco dopo averne tolto uno. */
export function neighbourAfterRemoval(items: WidgetItem[], uid: string): string | null {
  const index = items.findIndex((item) => item.uid === uid);
  return items[index + 1]?.uid ?? items[index - 1]?.uid ?? null;
}

/** Nome leggibile di un widget nella lista: il suo titolo (o il testo del banner), se no il tipo. */
export function summary(item: WidgetItem, types: WidgetType[]): string {
  const own = [item.data.title, item.data.text].find((value) => typeof value === "string" && value.trim());
  return typeof own === "string" ? own.trim() : (types.find((type) => type.type === item.type)?.label ?? item.type);
}

export function blankWidget(type: string): WidgetItem {
  return { uid: newUid(), type, data: {}, visibility: { mode: "all", pages: [] }, until: null };
}

/** Banner dal telefono (D-97): cambia il primo banner dell'area, o lo mette in cima. */
export function setNotice(items: WidgetItem[], data: Record<string, unknown>, until: string | null): WidgetItem[] {
  const current = items.find((item) => item.type === NOTICE);
  if (current) return items.map((item) => (item === current ? { ...item, data, until } : item));
  return [{ ...blankWidget(NOTICE), data, until }, ...items];
}

export function currentNotice(items: WidgetItem[]): WidgetItem | null {
  return items.find((item) => item.type === NOTICE) ?? null;
}
