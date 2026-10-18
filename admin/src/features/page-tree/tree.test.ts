import { describe, expect, it as test } from "vitest";
import { node } from "../../test/fakeApi";
import {
  childPath,
  createTargets,
  findNode,
  hasHome,
  height,
  moveTargets,
  needsPublishToTrash,
  placementLabel,
  reordered,
  statusLabels,
} from "./tree";

function sample() {
  const home = node("Home", { id: 1, is_home: true, slug: "", path: "/" });
  const l4 = node("Livello 4", { id: 5, parent_id: 4, path: "/a/b/c/d" });
  const l3 = node("Livello 3", { id: 4, parent_id: 3, path: "/a/b/c", children: [l4] });
  const l2 = node("Livello 2", { id: 3, parent_id: 2, path: "/a/b", children: [l3] });
  const a = node("A", { id: 2, path: "/a", children: [l2] });
  const b = node("B", { id: 6, path: "/b" });
  const c = node("C", { id: 7, path: "/c", children: [node("C1", { id: 8, parent_id: 7, path: "/c/c1" })] });
  return { roots: [home, a, b, c], home, a, b, c, l2, l3, l4 };
}

describe("albero delle pagine", () => {
  test("altezza, ricerca, homepage", () => {
    const { roots, a, l4 } = sample();
    expect(height(a)).toBe(4);
    expect(height(l4)).toBe(1);
    expect(findNode(roots, 4)?.title).toBe("Livello 3");
    expect(findNode(roots, null)).toBeNull();
    expect(hasHome(roots)).toBe(true);
    expect(hasHome(roots.slice(1))).toBe(false);
  });

  test("su e giù senza mai scavalcare la homepage", () => {
    const { roots } = sample();
    expect(reordered(roots, 6, -1)).toEqual([1, 6, 2, 7]);
    expect(reordered(roots, 6, 1)).toEqual([1, 2, 7, 6]);
    expect(reordered(roots, 2, -1)).toBeNull(); // sopra c'è la homepage
    expect(reordered(roots, 7, 1)).toBeNull(); // già l'ultima
    expect(reordered(roots, 1, 1)).toBeNull(); // la homepage resta in cima
    expect(reordered(roots, 99, 1)).toBeNull();
  });

  test("sposta: niente sé stessa, sottopagine, homepage, genitore attuale o oltre 4 livelli", () => {
    const { roots, a, b, l2, c } = sample();
    expect(moveTargets(roots, a)).toEqual([]); // alta 4: può stare solo in cima, dove già sta
    const forB = moveTargets(roots, b).map((t) => t.parentId);
    expect(forB).toEqual([2, 3, 4, 7, 8]);
    const forL2 = moveTargets(roots, l2).map((t) => t.parentId);
    expect(forL2).toEqual([null, 6, 7]); // alta 3: sotto pagine di livello 1
    expect(moveTargets(roots, roots[0]!)).toEqual([]);
    expect(moveTargets(roots, c).map((t) => t.parentId)).toEqual([2, 3, 6]);
  });

  test("crea: in cima o sotto una pagina che non è all'ultimo livello", () => {
    const { roots } = sample();
    expect(createTargets(roots).map((t) => t.parentId)).toEqual([null, 2, 3, 4, 6, 7, 8]);
    expect(placementLabel({ parentId: null, title: null, depth: 0 })).toBe("In cima (menu principale)");
    expect(placementLabel({ parentId: 4, title: "Livello 3", depth: 3 })).toBe('— — Sotto "Livello 3"');
  });

  test("indirizzo, stati e permesso per cestinare", () => {
    const { a } = sample();
    expect(childPath(a, "orari")).toBe("/a/orari");
    expect(childPath(null, "orari")).toBe("/orari");
    expect(childPath(node("Home", { path: "/" }), "x")).toBe("/x");
    const online = node("Online", { status: "published", has_draft: true });
    expect(statusLabels(online)).toEqual(["Online", "Modifiche non pubblicate"]);
    expect(statusLabels(node("Bozza", { has_draft: true }))).toEqual(["Bozza"]);
    expect(needsPublishToTrash(online)).toBe(true);
    expect(needsPublishToTrash(node("Prog", { publish_at: "2026-11-01T08:00:00+00:00" }))).toBe(true);
    expect(needsPublishToTrash(node("Bozza"))).toBe(false);
  });
});
