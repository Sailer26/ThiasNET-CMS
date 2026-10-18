// Controllo di un singolo campo come fa il server in bozza (app/services/blocks.py), con gli
// stessi messaggi. Solo le parole chiave elencate in tests/unit/test_blocks_registry.py (D-106).
import type { FieldSchema } from "../../../api/catalog";
import type { Data } from "../model/document";
import { isSafeUrl, normalizeUrl } from "./safeUrl";

export const MESSAGES = {
  type: "Tipo di dato non valido",
  enum: "Valore non ammesso",
  pattern: "Formato non valido",
  format: "Indirizzo non valido: usa https://, mailto:, tel: o un percorso con /",
  reserved: "Dato non valido",
  maxLength: (n: number) => `Al massimo ${n} caratteri`,
  maxItems: (n: number) => `Al massimo ${n} ${n === 1 ? "elemento" : "elementi"}`,
  minimum: (n: number) => `Il valore minimo è ${n}`,
  maximum: (n: number) => `Il valore massimo è ${n}`,
} as const;

/** Lunghezza come in Python: punti di codice, non unità UTF-16. */
export function length(text: string): number {
  return [...text].length;
}

function types(spec: FieldSchema): string[] {
  return spec.type === undefined ? [] : Array.isArray(spec.type) ? spec.type : [spec.type];
}

function typeOk(spec: FieldSchema, value: unknown): boolean {
  const allowed = types(spec);
  if (allowed.length === 0) return true;
  return allowed.some((type) => {
    if (type === "string") return typeof value === "string";
    if (type === "integer") return typeof value === "number" && Number.isInteger(value);
    if (type === "number") return typeof value === "number" && Number.isFinite(value);
    if (type === "boolean") return typeof value === "boolean";
    if (type === "array") return Array.isArray(value);
    if (type === "object") return value !== null && typeof value === "object" && !Array.isArray(value);
    return value === null && type === "null";
  });
}

/** Il problema di un valore (in bozza: i campi obbligatori non contano), o null. */
export function fieldProblem(spec: FieldSchema, value: unknown): string | null {
  if (value === undefined) return null;
  if (!typeOk(spec, value)) return MESSAGES.type;
  if (spec.enum && !spec.enum.includes(value as string | number)) return MESSAGES.enum;
  if (spec.not?.enum?.includes(value)) return MESSAGES.reserved;
  if (typeof value === "string") {
    if (spec.maxLength !== undefined && length(value) > spec.maxLength) return MESSAGES.maxLength(spec.maxLength);
    if (spec.pattern && !new RegExp(spec.pattern, "u").test(value)) return MESSAGES.pattern;
    if (spec.format === "safe-url" && !isSafeUrl(normalizeUrl(value))) return MESSAGES.format;
  }
  if (typeof value === "number") {
    if (spec.minimum !== undefined && value < spec.minimum) return MESSAGES.minimum(spec.minimum);
    if (spec.maximum !== undefined && value > spec.maximum) return MESSAGES.maximum(spec.maximum);
  }
  if (Array.isArray(value) && spec.maxItems !== undefined && value.length > spec.maxItems) {
    return MESSAGES.maxItems(spec.maxItems);
  }
  return null;
}

/** Schema di un campo con i rami allOf/if/then che valgono per questi dati (es. id del video). */
export function effectiveField(schema: FieldSchema, data: Data, field: string): FieldSchema {
  let spec: FieldSchema = schema.properties?.[field] ?? {};
  for (const branch of schema.allOf ?? []) {
    const conditions = Object.entries(branch.if?.properties ?? {});
    const applies = conditions.every(([key, cond]) => cond.const === undefined || data[key] === cond.const);
    const extra = branch.then?.properties?.[field];
    if (conditions.length > 0 && applies && extra) spec = { ...spec, ...extra };
  }
  return spec;
}
