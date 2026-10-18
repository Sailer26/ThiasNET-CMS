// Regole dell'albero delle pagine, pure e testabili (D-45, D-95). Il server ricontrolla tutto.
import type { PageNode } from "../../api/types";
import { it } from "../../text/it";

export const MAX_DEPTH = 4;

export interface Placement {
  parentId: number | null;
  title: string | null;
  depth: number;
}

export function height(node: PageNode): number {
  return 1 + Math.max(0, ...node.children.map(height));
}

function walk(nodes: PageNode[], depth: number, visit: (node: PageNode, depth: number) => void) {
  for (const node of nodes) {
    visit(node, depth);
    walk(node.children, depth + 1, visit);
  }
}

export function findNode(roots: PageNode[], id: number | null): PageNode | null {
  let found: PageNode | null = null;
  walk(roots, 1, (node) => {
    if (node.id === id) found = node;
  });
  return found;
}

export function hasHome(roots: PageNode[]): boolean {
  return roots.some((node) => node.is_home);
}

function ownIds(node: PageNode): Set<number> {
  const ids = new Set<number>();
  walk([node], 1, (child) => ids.add(child.id));
  return ids;
}

/** Nuovo ordine delle sorelle con `id` spostata di un posto, o null se non si può. */
export function reordered(siblings: PageNode[], id: number, delta: -1 | 1): number[] | null {
  const ids = siblings.map((node) => node.id);
  const from = ids.indexOf(id);
  const to = from + delta;
  const target = siblings[to];
  if (from < 0 || target === undefined || target.is_home || siblings[from]?.is_home) return null;
  const next = [...ids];
  next[from] = target.id;
  next[to] = id;
  return next;
}

/** Dove si può spostare una pagina: mai sotto sé stessa, sotto la homepage o oltre 4 livelli. */
export function moveTargets(roots: PageNode[], node: PageNode): Placement[] {
  if (node.is_home) return [];
  const size = height(node);
  const banned = ownIds(node);
  const targets: Placement[] = [];
  if (node.parent_id !== null) targets.push({ parentId: null, title: null, depth: 0 });
  walk(roots, 1, (candidate, depth) => {
    if (banned.has(candidate.id) || candidate.is_home || candidate.id === node.parent_id) return;
    if (depth + size > MAX_DEPTH) return;
    targets.push({ parentId: candidate.id, title: candidate.title, depth });
  });
  return targets;
}

/** Dove si può creare una pagina nuova: in cima o sotto una pagina che non è all'ultimo livello. */
export function createTargets(roots: PageNode[]): Placement[] {
  const targets: Placement[] = [{ parentId: null, title: null, depth: 0 }];
  walk(roots, 1, (candidate, depth) => {
    if (candidate.is_home || depth >= MAX_DEPTH) return;
    targets.push({ parentId: candidate.id, title: candidate.title, depth });
  });
  return targets;
}

export function childPath(parent: PageNode | null, slug: string): string {
  const base = parent ? parent.path.replace(/\/+$/, "") : "";
  return `${base}/${slug}`;
}

/** Una pagina online (o programmata) si toglie solo con il permesso di pubblicare. */
export function needsPublishToTrash(node: PageNode): boolean {
  return node.status !== "draft" || node.publish_at !== null;
}

export function statusLabels(node: PageNode): string[] {
  const labels: string[] = [it.tree.status[node.status]];
  if (node.has_draft && node.status !== "draft") labels.push(it.tree.status.changes);
  return labels;
}

export function placementLabel(placement: Placement): string {
  if (placement.parentId === null) return it.move.top;
  return `${"— ".repeat(Math.max(0, placement.depth - 1))}${it.move.under(placement.title ?? "")}`;
}
