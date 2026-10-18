import { describe, expect, it as test } from "vitest";
import { announcements, dropIndex, instructions } from "./sortable";

describe("trascinamento dentro una zona (D-109)", () => {
  test("posizione finale", () => {
    const order = ["a", "b", "c"];
    expect(dropIndex(order, "a", "c")).toBe(2);
    expect(dropIndex(order, "c", "a")).toBe(0);
    expect(dropIndex(order, "a", "a")).toBeNull();
    expect(dropIndex(order, "a", null)).toBeNull();
    expect(dropIndex(order, "x", "a")).toBeNull();
  });

  test("annunci e istruzioni in italiano", () => {
    const say = announcements(
      (id) => ({ a: "Testo", b: "Immagine" })[id] ?? "",
      (id) => ["a", "b"].indexOf(id) + 1,
    );
    const a = { id: "a" } as never;
    const b = { id: "b" } as never;
    expect(say.onDragStart({ active: a })).toBe("Hai preso il blocco Testo.");
    expect(say.onDragOver({ active: a, over: b })).toBe("Il blocco Testo è sulla posizione 2.");
    expect(say.onDragOver({ active: a, over: null })).toBeUndefined();
    expect(say.onDragEnd({ active: a, over: b })).toBe("Blocco Testo lasciato nella posizione 2.");
    expect(say.onDragEnd({ active: a, over: null })).toBe("Blocco Testo lasciato dov'era.");
    expect(say.onDragCancel({ active: a, over: null })).toBe("Spostamento del blocco Testo annullato.");
    expect(instructions.draggable).toMatch(/spazio o invio/);
  });
});
