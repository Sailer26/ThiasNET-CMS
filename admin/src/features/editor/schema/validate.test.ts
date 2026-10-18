import { describe, expect, it as test } from "vitest";
import { catalog, sharedCases } from "../../../test/catalog";
import { completeUrl, isSafeUrl, normalizeUrl } from "./safeUrl";
import { effectiveField, fieldProblem, length } from "./validate";

const cases = sharedCases();

describe("stesso verdetto del server (casi condivisi)", () => {
  test.each(cases.safe)("link ammesso: %s", (url) => expect(isSafeUrl(url)).toBe(true));
  test.each(cases.unsafe)("link rifiutato: %s", (url) => expect(isSafeUrl(url)).toBe(false));
  test.each(cases.normalized)("normalizza %s", (raw, clean) => expect(normalizeUrl(raw)).toBe(clean));
  test.each(cases.fields)("$block.$field = $value", ({ block, field, value, ok }) => {
    const schema = catalog().types[block]!.schema;
    expect(fieldProblem(effectiveField(schema, { [field]: value }, field), value) === null).toBe(ok);
  });
});

describe("controllo dei campi", () => {
  const spec = { type: "string", maxLength: 3 } as const;

  test("lunghezza in punti di codice, come in Python", () => {
    expect(length("😀😀")).toBe(2);
    expect(fieldProblem(spec, "😀😀😀")).toBeNull();
    expect(fieldProblem(spec, "abcd")).toBe("Al massimo 3 caratteri");
  });

  test("tipi, minimo e massimo, elementi, vuoti", () => {
    expect(fieldProblem({ type: "integer" }, 1.5)).toBe("Tipo di dato non valido");
    expect(fieldProblem({ type: "number", minimum: 0 }, -1)).toBe("Il valore minimo è 0");
    expect(fieldProblem({ type: "number", maximum: 1 }, 2)).toBe("Il valore massimo è 1");
    expect(fieldProblem({ type: "array", maxItems: 1 }, [1, 2])).toBe("Al massimo 1 elemento");
    expect(fieldProblem({ type: "boolean" }, "si")).toBe("Tipo di dato non valido");
    expect(fieldProblem({ type: ["string", "null"] }, null)).toBeNull();
    expect(fieldProblem(spec, undefined)).toBeNull();
  });

  test("il codice del video dipende dalla piattaforma", () => {
    const video = catalog().types.video!.schema;
    const youtube = effectiveField(video, { provider: "youtube" }, "video_id");
    const vimeo = effectiveField(video, { provider: "vimeo" }, "video_id");
    expect(fieldProblem(youtube, "dQw4w9WgXcQ")).toBeNull();
    expect(fieldProblem(youtube, "123")).toBe("Formato non valido");
    expect(fieldProblem(vimeo, "123")).toBeNull();
    expect(fieldProblem(vimeo, "dQw4w9WgXcQ")).toBe("Formato non valido");
  });

  test("www. diventa https:// uscendo dal campo", () => {
    expect(completeUrl(" www.comune.ch ")).toBe("https://www.comune.ch");
    expect(completeUrl("/contatti")).toBe("/contatti");
  });
});
