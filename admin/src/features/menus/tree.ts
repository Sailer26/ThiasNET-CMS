// Operazioni sull'albero del menu (D-145): funzioni pure, ogni volta un albero nuovo.
import type { MenuItemData } from "../../api/menus";

export type MenuItem = MenuItemData;

export function newUid(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Elenco di sorelle che contiene la voce, con la posizione; null se non c'è. */
function siblings(items: MenuItem[], uid: string): { list: MenuItem[]; index: number } | null {
  const index = items.findIndex((item) => item.uid === uid);
  if (index >= 0) return { list: items, index };
  for (const item of items) {
    const found = siblings(item.children, uid);
    if (found) return found;
  }
  return null;
}

/** Sostituisce un elenco di sorelle (riconosciuto per identità) dentro l'albero. */
function replaceList(items: MenuItem[], target: MenuItem[], next: MenuItem[]): MenuItem[] {
  if (items === target) return next;
  return items.map((item) => {
    const children = replaceList(item.children, target, next);
    return children === item.children ? item : { ...item, children };
  });
}

export function depthOf(items: MenuItem[], uid: string, depth = 1): number {
  for (const item of items) {
    if (item.uid === uid) return depth;
    const found = depthOf(item.children, uid, depth + 1);
    if (found) return found;
  }
  return 0;
}

function height(item: MenuItem): number {
  return 1 + Math.max(0, ...item.children.map(height));
}

export function moveBy(items: MenuItem[], uid: string, delta: number): MenuItem[] {
  const found = siblings(items, uid);
  if (!found) return items;
  const to = found.index + delta;
  if (to < 0 || to >= found.list.length) return items;
  const next = [...found.list];
  const [moved] = next.splice(found.index, 1);
  next.splice(to, 0, moved!);
  return replaceList(items, found.list, next);
}

export function reorder(items: MenuItem[], active: string, over: string): MenuItem[] {
  const from = siblings(items, active);
  const to = siblings(items, over);
  if (!from || !to || from.list !== to.list || active === over) return items; // solo tra sorelle
  return moveBy(items, active, to.index - from.index);
}

export function canIndent(items: MenuItem[], uid: string, maxDepth: number): boolean {
  const found = siblings(items, uid);
  if (!found || found.index === 0) return false;
  const item = found.list[found.index]!;
  return depthOf(items, uid) + height(item) <= maxDepth;
}

/** Diventa l'ultima sottovoce della voce precedente. */
export function indent(items: MenuItem[], uid: string, maxDepth: number): MenuItem[] {
  if (!canIndent(items, uid, maxDepth)) return items;
  const found = siblings(items, uid)!;
  const item = found.list[found.index]!;
  const previous = found.list[found.index - 1]!;
  const next = found.list
    .filter((other) => other.uid !== uid)
    .map((other) => (other === previous ? { ...previous, children: [...previous.children, item] } : other));
  return replaceList(items, found.list, next);
}

/** Esce dal genitore e va subito dopo di lui. */
export function outdent(items: MenuItem[], uid: string): MenuItem[] {
  const parentOf = (list: MenuItem[]): MenuItem | null => {
    for (const item of list) {
      if (item.children.some((child) => child.uid === uid)) return item;
      const deeper = parentOf(item.children);
      if (deeper) return deeper;
    }
    return null;
  };
  const parent = parentOf(items);
  if (!parent) return items;
  const outer = siblings(items, parent.uid)!;
  const item = parent.children.find((child) => child.uid === uid)!;
  const lighter = { ...parent, children: parent.children.filter((child) => child.uid !== uid) };
  const next = [...outer.list];
  next.splice(outer.index, 1, lighter, item);
  return replaceList(items, outer.list, next);
}

export function removeItem(items: MenuItem[], uid: string): MenuItem[] {
  return items
    .filter((item) => item.uid !== uid)
    .map((item) => {
      const children = removeItem(item.children, uid);
      return children.length === item.children.length ? item : { ...item, children };
    });
}

export function replaceItem(items: MenuItem[], uid: string, change: (item: MenuItem) => MenuItem): MenuItem[] {
  return items.map((item) =>
    item.uid === uid ? change(item) : { ...item, children: replaceItem(item.children, uid, change) },
  );
}
