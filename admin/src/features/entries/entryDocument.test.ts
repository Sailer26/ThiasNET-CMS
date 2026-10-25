import { describe, expect, it as test } from "vitest";
import type { FieldSchema } from "../../api/catalog";
import type { EntryDocument } from "../../api/entries";
import { startHistory } from "../editor/model/history";
import { entrySafe, firstField, historyReducer, mediaIdsOf, setField, setSeo } from "./entryDocument";

const SCHEMA: FieldSchema = {
  type: "object",
  properties: {
    date: { type: "string", title: "Data", "x-date": true, maxLength: 10 },
    cover: { type: "integer", title: "Copertina", "x-media": "image", minimum: 1 },
    summary: { type: "string", title: "Riassunto", "x-multiline": true, maxLength: 10 },
  },
};
const DOC: EntryDocument = { title: "Festa", fields: { date: "2026-10-25" }, seo: {} };

describe("documento della notizia (7b)", () => {
  test("campi e SEO cambiano su una copia", () => {
    const next = setField(DOC, "summary", "Ciao");
    expect(next.fields).toEqual({ date: "2026-10-25", summary: "Ciao" });
    expect(DOC.fields).toEqual({ date: "2026-10-25" });
    expect(setField(next, "summary", undefined).fields).toEqual({ date: "2026-10-25" });
    expect(setSeo(DOC, "description", "x").seo).toEqual({ description: "x" });
  });

  test("un campo scritto a metà: si salva l'ultimo valore valido", () => {
    const typing = setField(DOC, "date", "2026-10-3");
    const { doc, problems } = entrySafe(typing, SCHEMA, DOC);
    expect(doc.fields.date).toBe("2026-10-25");
    expect(problems.get("date")).toBe("Data non valida");
    expect(entrySafe({ ...DOC, fields: { old: 1 } }, SCHEMA, null).doc.fields).toEqual({});
  });

  test("media del documento e primo campo di un tipo", () => {
    expect(mediaIdsOf({ ...DOC, fields: { cover: 7 }, seo: { og_image_media_id: 9 } }, SCHEMA)).toEqual([7, 9]);
    expect(firstField(SCHEMA, (spec) => Boolean(spec["x-multiline"]))).toBe("summary");
    expect(firstField(SCHEMA, (spec) => Boolean(spec["x-datetime"]))).toBeNull();
  });

  test("annulla e ripristina", () => {
    let state = startHistory(DOC);
    state = historyReducer(state, { type: "edit", fn: (d) => setField(d, "summary", "Ciao"), key: null, at: 1 });
    state = historyReducer(state, { type: "undo" });
    expect(state.present).toBe(DOC);
    state = historyReducer(state, { type: "redo" });
    expect(state.present.fields.summary).toBe("Ciao");
  });
});
