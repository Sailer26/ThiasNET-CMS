import { describe, expect, it as test } from "vitest";
import type { WidgetItem, WidgetType } from "../../api/widgets";
import { isoToZurich } from "../editor/schedule/siteTime";
import { currentNotice, moveBy, neighbourAfterRemoval, removeWidget, replaceWidget, setNotice, summary } from "./model";
import { nextUntil, NO_END, untilFields, untilIso } from "./UntilFields";

const A: WidgetItem = { uid: "a".repeat(32), type: "text", data: { title: "Chi siamo" } };
const B: WidgetItem = { uid: "b".repeat(32), type: "hours", data: {} };
const N: WidgetItem = { uid: "c".repeat(32), type: "notice", data: { text: "Chiuso", level: "info" }, until: null };
const TYPES: WidgetType[] = [{ type: "hours", label: "Orari", schema: {} }];

describe("lista dei widget (6c)", () => {
  test("su e giù senza uscire dai bordi, sempre una lista nuova", () => {
    const items = [A, B];
    expect(moveBy(items, B.uid, -1)).toEqual([B, A]);
    expect(moveBy(items, A.uid, -1)).toBe(items);
    expect(moveBy(items, B.uid, 1)).toBe(items);
    expect(items).toEqual([A, B]);
  });

  test("togli, sostituisci o aggiungi; il vicino dopo la rimozione", () => {
    expect(removeWidget([A, B], A.uid)).toEqual([B]);
    expect(replaceWidget([A, B], { ...A, data: { title: "Nuovo" } })[0]?.data.title).toBe("Nuovo");
    expect(replaceWidget([A], B)).toEqual([A, B]);
    expect(neighbourAfterRemoval([A, B], A.uid)).toBe(B.uid);
    expect(neighbourAfterRemoval([A, B], B.uid)).toBe(A.uid);
    expect(neighbourAfterRemoval([A], A.uid)).toBeNull();
  });

  test("nome nella lista: titolo, testo del banner, altrimenti il tipo", () => {
    expect(summary(A, TYPES)).toBe("Chi siamo");
    expect(summary(N, TYPES)).toBe("Chiuso");
    expect(summary(B, TYPES)).toBe("Orari");
  });

  test("banner dal telefono: cambia il primo o lo mette in cima", () => {
    const changed = setNotice([A, N], { text: "Aperto", level: "warning" }, null);
    expect(changed).toHaveLength(2);
    expect(currentNotice(changed)).toMatchObject({ uid: N.uid, data: { text: "Aperto" } });
    const added = setNotice([A], { text: "Nuovo" }, "2099-01-10T08:00:00+01:00");
    expect(added[0]).toMatchObject({ type: "notice", until: "2099-01-10T08:00:00+01:00", visibility: { mode: "all", pages: [] } });
    expect(added[1]).toBe(A);
  });
});

describe("fino al (ora svizzera)", () => {
  test("vuoto vuol dire senza scadenza; giorno senza ora vale fino a fine giornata", () => {
    expect(untilIso({ date: "", time: "" })).toBeNull();
    expect(untilIso({ date: "2099-01-10", time: "" })).toBe("2099-01-10T23:59:00+01:00");
    expect(untilIso({ date: "2099-07-10", time: "08:00" })).toBe("2099-07-10T08:00:00+02:00");
  });

  test("date passate o impossibili sono errori leggibili", () => {
    expect(() => untilIso({ date: "2020-01-10", time: "08:00" })).toThrow(/già passati/);
    expect(() => untilIso({ date: "2099-02-31", time: "08:00" })).toThrow(/non validi/);
  });

  test("dall'istante salvato ai campi del modulo", () => {
    expect(isoToZurich("2099-01-10T07:00:00+00:00")).toEqual({ date: "2099-01-10", time: "08:00" });
    expect(isoToZurich("non una data")).toBeNull();
  });
});

describe("fino al già salvato", () => {
  test("uno scaduto non si propone; uno futuro sì", () => {
    expect(untilFields("2020-01-10T07:00:00+00:00")).toEqual(NO_END);
    expect(untilFields("2099-01-10T07:00:00+00:00")).toEqual({ date: "2099-01-10", time: "08:00" });
  });

  test("se non lo si tocca resta il valore salvato; se lo si cambia si converte", () => {
    const start = { date: "2099-01-10", time: "08:00" };
    expect(nextUntil(start, start, "2099-01-10T07:00:00+00:00")).toBe("2099-01-10T07:00:00+00:00");
    expect(nextUntil({ date: "2099-01-11", time: "08:00" }, start, "x")).toBe("2099-01-11T08:00:00+01:00");
    expect(nextUntil(NO_END, start, "x")).toBeNull();
  });
});
