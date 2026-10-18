import { describe, expect, it as test } from "vitest";
import { catalog } from "../../../test/catalog";
import type { PageDocument } from "./document";
import { draftSafe, problemKey } from "./draftSafe";
import { isFieldErrors, locateError } from "./errorPaths";

const UID = "a".repeat(32);

function page(data: Record<string, unknown>, type = "cta"): PageDocument {
  return { title: "x", layout: "page", seo: {}, zones: { main: [{ uid: UID, type, variant: null, data }] } };
}

describe("salvataggio di campi scritti a metà", () => {
  test("un campo non valido manda l'ultimo valore valido salvato", () => {
    const saved = page({ title: "Vieni", url: "/contatti" });
    const { doc, problems } = draftSafe(page({ title: "Vieni!", url: "htt" }), catalog(), saved);
    expect(doc.zones.main![0]!.data).toEqual({ title: "Vieni!", url: "/contatti" });
    expect(problems.get(problemKey(UID, ["url"]))).toMatch(/Indirizzo non valido/);
  });

  test("senza un valore valido precedente il campo resta fuori", () => {
    const { doc, problems } = draftSafe(page({ url: "www.sito" }), catalog(), null);
    expect(doc.zones.main![0]!.data).toEqual({});
    expect(problems.size).toBe(1);
  });

  test("anche dentro gli elenchi (didascalie della galleria)", () => {
    const long = "x".repeat(201);
    const { doc, problems } = draftSafe(
      page({ items: [{ media_id: 1, caption: long }] }, "gallery"),
      catalog(),
      page({ items: [{ media_id: 1, caption: "Lago" }] }, "gallery"),
    );
    expect(doc.zones.main![0]!.data).toEqual({ items: [{ media_id: 1, caption: "Lago" }] });
    expect([...problems.keys()]).toEqual([problemKey(UID, ["items", 0, "caption"])]);
  });

  test("tipo di blocco sconosciuto: invariato (decide il server)", () => {
    const strange = page({ x: 1 }, "sconosciuto");
    expect(draftSafe(strange, catalog(), null).doc).toEqual(strange);
  });
});

describe("errori del server sui campi", () => {
  const sent = page({ items: [] }, "gallery");

  test("percorsi tradotti nel blocco e nel campo della copia inviata", () => {
    expect(locateError("zones/main/0/data/items/2/media_id", sent)).toEqual({
      kind: "block", zone: "main", index: 0, uid: UID, field: "items/2/media_id",
    });
    expect(locateError("zones/main/0/variant", sent)).toMatchObject({ kind: "block", field: "variant" });
    expect(locateError("zones/main", sent)).toEqual({ kind: "zone", zone: "main" });
    expect(locateError("seo/description", sent)).toEqual({ kind: "seo", field: "description" });
    expect(locateError("layout", sent)).toEqual({ kind: "page", field: "layout" });
    expect(locateError("title", sent)).toEqual({ kind: "page", field: "title" });
    expect(locateError("zones/main/7/data/x", sent)).toMatchObject({ uid: null });
  });

  test("riconosce l'elenco degli errori", () => {
    expect(isFieldErrors([{ path: "title", code: "x", message: "y" }])).toBe(true);
    expect(isFieldErrors({ path: "title" })).toBe(false);
    expect(isFieldErrors([null])).toBe(false);
  });
});
