// Catalogo finto per i test: gli schemi veri dai file, layout e varianti come il tema default.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { Catalog, FieldSchema } from "../api/catalog";

const BLOCKS = resolve(process.cwd(), "..", "app", "blocks");
const TYPES = [
  "hero", "heading", "text", "image", "text_image", "gallery", "cta",
  "quote", "video", "files", "map", "contacts", "divider",
];
const MAIN = TYPES.filter((type) => type !== "hero");

function schema(type: string): FieldSchema {
  return JSON.parse(readFileSync(resolve(BLOCKS, `${type}.schema.json`), "utf8")) as FieldSchema;
}

export function catalog(): Catalog {
  return {
    types: Object.fromEntries(TYPES.map((type) => [type, { label: schema(type).title ?? type, schema: schema(type) }])),
    layouts: {
      home: {
        label: "Homepage",
        zones: {
          hero: { label: "Apertura", blocks: ["hero"], max: 1 },
          main: { label: "Contenuto principale", blocks: MAIN, max: null },
        },
      },
      page: {
        label: "Pagina standard",
        zones: {
          main: { label: "Contenuto principale", blocks: MAIN, max: null },
          sidebar: { label: "Barra laterale", blocks: ["text", "cta", "image"], max: 4 },
        },
      },
      full: {
        label: "Pagina larga",
        zones: { main: { label: "Contenuto principale", blocks: MAIN.filter((t) => t !== "contacts"), max: null } },
      },
    },
    variants: {
      text_image: {
        default: "image_left",
        options: {
          image_left: { label: "Immagine a sinistra", thumbnail: "variants/a.png", thumbnail_url: "/assets/variants/a.png?v=1" },
          image_right: { label: "Immagine a destra", thumbnail: "variants/b.png", thumbnail_url: "/assets/variants/b.png?v=1" },
        },
      },
    },
    locales: ["it", "de"],
  };
}

export function sharedCases(): {
  safe: string[];
  unsafe: string[];
  normalized: [string, string][];
  fields: { block: string; field: string; value: unknown; ok: boolean }[];
} {
  return JSON.parse(readFileSync(resolve(process.cwd(), "..", "tests", "fixtures", "safe_url_cases.json"), "utf8"));
}
