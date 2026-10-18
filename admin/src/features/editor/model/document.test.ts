import { describe, expect, it as test } from "vitest";
import { catalog } from "../../../test/catalog";
import {
  addBlock,
  duplicateBlock,
  getPath,
  hasRoom,
  locate,
  moveBlock,
  newBlock,
  normalize,
  removeBlock,
  setPath,
  setSeo,
  setTitle,
  setVariant,
  shiftBlock,
  uids,
  updateField,
  zonesFor,
  type PageDocument,
} from "./document";
import { relayout } from "./relayout";
import { newUid, UID_RE } from "./uid";

const u = (n: number) => String(n).padStart(32, "0");

function doc(): PageDocument {
  return {
    title: "Chi siamo",
    layout: "page",
    seo: {},
    zones: {
      main: [
        { uid: u(1), type: "heading", variant: null, data: { text: "Benvenuti", level: 2 } },
        { uid: u(2), type: "text", variant: null, data: { body: "<p>Ciao</p>" } },
        { uid: u(3), type: "gallery", variant: null, data: { items: [{ media_id: 4 }, { media_id: 5 }] } },
      ],
      sidebar: [{ uid: u(4), type: "cta", variant: null, data: { title: "Scrivici" } }],
    },
  };
}

describe("documento della pagina", () => {
  test("uid: 32 esadecimali, mai uno già usato", () => {
    const uid = newUid(new Set([u(1)]));
    expect(uid).toMatch(UID_RE);
    expect(uids(doc())).toEqual(new Set([u(1), u(2), u(3), u(4)]));
  });

  test("percorsi: impostare, leggere, togliere senza toccare l'originale", () => {
    const data = { items: [{ media_id: 4, caption: "a" }] };
    const next = setPath(data, ["items", 0, "caption"], undefined);
    expect(next).toEqual({ items: [{ media_id: 4 }] });
    expect(data.items[0]!.caption).toBe("a");
    expect(getPath(next, ["items", 0, "media_id"])).toBe(4);
    expect(getPath(next, ["nulla", 3])).toBeUndefined();
    expect(setPath(undefined, ["a"], 1)).toEqual({ a: 1 });
  });

  test("campi, varianti, titolo e SEO", () => {
    const original = doc();
    const edited = updateField(original, u(1), ["text"], "Ciao a tutti");
    expect(locate(edited, u(1))!.block.data.text).toBe("Ciao a tutti");
    expect(locate(original, u(1))!.block.data.text).toBe("Benvenuti");
    expect(locate(setVariant(original, u(2), "dark"), u(2))!.block.variant).toBe("dark");
    expect(setTitle(original, "Nuovo").title).toBe("Nuovo");
    expect(setSeo(setSeo(original, "title", "T"), "title", undefined).seo).toEqual({});
  });

  test("aggiungere, togliere, spostare, duplicare", () => {
    const base = doc();
    const added = addBlock(base, "main", newBlock(catalog(), "map", u(9)), 1);
    expect(added.zones.main!.map((b) => b.uid)).toEqual([u(1), u(9), u(2), u(3)]);
    expect(locate(added, u(9))!.block.data).toEqual({ zoom: 15 });
    expect(locate(removeBlock(base, u(2)), u(2))).toBeNull();
    expect(shiftBlock(base, u(1), 1).zones.main!.map((b) => b.uid)).toEqual([u(2), u(1), u(3)]);
    expect(shiftBlock(base, u(1), -1)).toBe(base);
    expect(moveBlock(base, u(2), "sidebar", 0).zones.sidebar!.map((b) => b.uid)).toEqual([u(2), u(4)]);
    const copy = duplicateBlock(base, u(3), u(8));
    expect(copy.zones.main!.map((b) => b.uid)).toEqual([u(1), u(2), u(3), u(8)]);
    expect(locate(copy, u(8))!.block.data).not.toBe(locate(copy, u(3))!.block.data);
    expect(newBlock(catalog(), "text_image", u(7)).variant).toBe("image_left");
  });

  test("posto nelle zone e zone ammesse", () => {
    const full = { ...doc(), zones: { ...doc().zones, sidebar: [1, 2, 3, 4].map((n) => newBlock(catalog(), "text", u(20 + n))) } };
    expect(hasRoom(full, catalog(), "sidebar")).toBe(false);
    expect(hasRoom(full, catalog(), "main")).toBe(true);
    expect(zonesFor(doc(), catalog(), "text", "main")).toEqual(["sidebar"]);
    expect(zonesFor(full, catalog(), "text", "main")).toEqual([]);
    expect(zonesFor(doc(), catalog(), "map")).toEqual(["main"]);
  });

  test("normalizza: zone del layout, varianti di default, layout sparito", () => {
    const loose: PageDocument = {
      title: "x",
      layout: "sparito",
      seo: undefined as never,
      zones: { main: [{ uid: u(1), type: "text_image", variant: null, data: {} }], vecchia: [] },
    };
    const clean = normalize(loose, catalog(), "page");
    expect(clean.layout).toBe("page");
    expect(Object.keys(clean.zones)).toEqual(["main", "sidebar"]);
    expect(clean.zones.main![0]!.variant).toBe("image_left");
    expect(clean.seo).toEqual({});
  });

  test("cambio del tipo di pagina: stessa zona, prima zona libera, scartati elencati", () => {
    const toFull = relayout(doc(), catalog(), "full");
    expect(Object.keys(toFull.doc.zones)).toEqual(["main"]);
    expect(toFull.doc.zones.main!.map((b) => b.uid)).toEqual([u(1), u(2), u(3), u(4)]);
    expect(toFull.dropped).toEqual([]);
    const withContacts = addBlock(doc(), "main", newBlock(catalog(), "contacts", u(6)));
    expect(relayout(withContacts, catalog(), "full").dropped.map((b) => b.uid)).toEqual([u(6)]);
    const home = relayout(doc(), catalog(), "home");
    expect(home.doc.zones.hero).toEqual([]);
    expect(relayout(doc(), catalog(), "nessuno").doc).toEqual(doc());
  });
});
