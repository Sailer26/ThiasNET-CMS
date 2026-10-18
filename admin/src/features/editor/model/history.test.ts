import { describe, expect, it as test } from "vitest";
import type { PageDocument } from "./document";
import { commit, HISTORY_LIMIT, MERGE_MS, redo, startHistory, undo } from "./history";

const page = (title: string): PageDocument => ({ title, layout: "page", seo: {}, zones: {} });

describe("annulla e ripristina", () => {
  test("annulla e ripristina; una modifica nuova cancella il futuro", () => {
    let h = startHistory(page("a"));
    h = commit(h, page("b"), null, 0);
    h = commit(h, page("c"), null, 0);
    h = undo(h);
    expect(h.present.title).toBe("b");
    h = redo(h);
    expect(h.present.title).toBe("c");
    h = commit(undo(h), page("d"), null, 0);
    expect(h.future).toEqual([]);
    expect(redo(h)).toBe(h);
    expect(undo(startHistory(page("x")))).toEqual(startHistory(page("x")));
  });

  test("le battute nello stesso campo entro un secondo sono un passo solo", () => {
    let h = startHistory(page(""));
    h = commit(h, page("C"), "u:title", 1000);
    h = commit(h, page("Ci"), "u:title", 1000 + MERGE_MS);
    h = commit(h, page("Cia"), "u:title", 1000 + MERGE_MS * 3);
    h = commit(h, page("Ciao"), "u:altro", 1000 + MERGE_MS * 3);
    expect(h.past.map((d) => d.title)).toEqual(["", "Ci", "Cia"]);
    expect(undo(h).present.title).toBe("Cia");
  });

  test("al massimo 100 passi; lo stesso documento non è un passo", () => {
    let h = startHistory(page("0"));
    for (let i = 1; i <= HISTORY_LIMIT + 20; i += 1) h = commit(h, page(String(i)), null, i);
    expect(h.past).toHaveLength(HISTORY_LIMIT);
    expect(commit(h, h.present, null, 0)).toBe(h);
  });
});
