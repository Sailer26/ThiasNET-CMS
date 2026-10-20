import { describe, expect, it as test } from "vitest";
import { canIndent, indent, moveBy, neighbourAfterRemoval, outdent, positionOf, removeItem, reorder, type MenuItem } from "./tree";

const leaf = (uid: string, children: MenuItem[] = []): MenuItem => ({ uid, url: `/${uid}`, label: uid, children });
const uids = (items: MenuItem[]): unknown => items.map((i) => (i.children.length ? { [i.uid]: uids(i.children) } : i.uid));

describe("albero del menu (operazioni pure)", () => {
  const base = [leaf("a"), leaf("b", [leaf("b1")]), leaf("c")];

  test("su e giù tra sorelle, senza uscire dai bordi", () => {
    expect(uids(moveBy(base, "c", -1))).toEqual(["a", "c", { b: ["b1"] }]);
    expect(moveBy(base, "a", -1)).toBe(base);
  });

  test("rientra sotto la voce precedente, solo se i livelli lo permettono", () => {
    expect(uids(indent(base, "c", 2))).toEqual(["a", { b: ["b1", "c"] }]);
    expect(canIndent(base, "a", 2)).toBe(false); // nessuna voce prima
    expect(canIndent(base, "b", 2)).toBe(false); // b ha già figli: diventerebbero un terzo livello
    expect(canIndent(base, "c", 1)).toBe(false);
  });

  test("esce dal genitore e va subito dopo", () => {
    expect(uids(outdent(base, "b1"))).toEqual(["a", "b", "b1", "c"]);
  });

  test("dopo Togli il focus va alla voce dopo, prima o al genitore", () => {
    expect(neighbourAfterRemoval(base, "a")).toBe("b");
    expect(neighbourAfterRemoval(base, "c")).toBe("b");
    expect(neighbourAfterRemoval(base, "b1")).toBe("b");
    expect(positionOf(base, "c")).toEqual({ position: 3, count: 3 });
  });

  test("togli e trascina", () => {
    expect(uids(removeItem(base, "b"))).toEqual(["a", "c"]);
    expect(uids(reorder(base, "a", "c"))).toEqual([{ b: ["b1"] }, "c", "a"]);
    expect(uids(reorder(base, "b1", "a"))).toEqual(uids(base)); // solo tra sorelle
  });
});
