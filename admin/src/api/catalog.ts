// Catalogo dei blocchi (GET /api/admin/blocks): schemi, layout con zone, varianti del tema.
import { request } from "./client";

export interface FieldSchema {
  type?: string | string[];
  title?: string;
  description?: string;
  maxLength?: number;
  pattern?: string;
  format?: string;
  enum?: (string | number)[];
  "x-enum-titles"?: string[];
  default?: unknown;
  minimum?: number;
  maximum?: number;
  items?: FieldSchema;
  minItems?: number;
  maxItems?: number;
  properties?: Record<string, FieldSchema>;
  required?: string[];
  dependentRequired?: Record<string, string[]>;
  "x-media"?: "image" | "file";
  "x-richtext"?: boolean;
  /** Raccolte (7b): testo lungo, data "AAAA-MM-GG", data e ora con il fuso (ora svizzera). */
  "x-multiline"?: boolean;
  "x-date"?: boolean;
  "x-datetime"?: boolean;
  /** Impostazioni d'aspetto (D-143): le scelte sono colori della palette del tema. */
  "x-color"?: boolean;
  not?: { enum?: unknown[] };
  const?: unknown;
  allOf?: { if?: FieldSchema; then?: FieldSchema }[];
  additionalProperties?: boolean;
}

export interface BlockType {
  label: string;
  schema: FieldSchema;
}

export interface Zone {
  label: string;
  blocks: string[];
  max: number | null;
}

export interface Layout {
  label: string;
  zones: Record<string, Zone>;
}

export interface VariantOption {
  label: string;
  thumbnail: string;
  thumbnail_url: string;
}

export interface Variants {
  default: string;
  options: Record<string, VariantOption>;
}

export interface Catalog {
  types: Record<string, BlockType>;
  layouts: Record<string, Layout>;
  variants: Record<string, Variants>;
  locales: string[];
}

let cached: Promise<Catalog> | null = null;

/** Il catalogo cambia solo con un deploy del tema: una richiesta per sessione del pannello. */
export function fetchCatalog(): Promise<Catalog> {
  cached ??= request<Catalog>("GET", "/blocks").then(
    (result) => result.data,
    (error: unknown) => {
      cached = null; // un errore non resta in memoria: la prossima volta si riprova
      throw error;
    },
  );
  return cached;
}

export function forgetCatalog(): void {
  cached = null;
}
