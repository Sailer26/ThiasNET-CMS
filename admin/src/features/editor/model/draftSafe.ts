// Prima di salvare o mandare all'anteprima (D-104): un campo scritto a metà non deve far
// fallire tutta la pagina. Si manda l'ultimo valore valido già salvato, oppure niente.
import type { Catalog, FieldSchema } from "../../../api/catalog";
import { effectiveField, fieldProblem } from "../schema/validate";
import { locate, type BlockDoc, type Data, type PageDocument } from "./document";

export interface Unsaved {
  /** "uid:percorso/del/campo" → messaggio */
  problems: Map<string, string>;
}

export function problemKey(uid: string, path: (string | number)[]): string {
  return `${uid}:${path.join("/")}`;
}

function cleanItems(
  spec: FieldSchema,
  value: unknown,
  previous: unknown,
  uid: string,
  field: string,
  problems: Map<string, string>,
): unknown {
  const itemSpec = spec.items;
  if (!Array.isArray(value) || !itemSpec?.properties) return value;
  return value.map((item, index) => {
    const before = Array.isArray(previous) ? (previous[index] as Data | undefined) : undefined;
    return cleanData(itemSpec, (item ?? {}) as Data, before ?? {}, uid, [field, index], problems);
  });
}

function cleanData(
  schema: FieldSchema,
  data: Data,
  previous: Data,
  uid: string,
  prefix: (string | number)[],
  problems: Map<string, string>,
): Data {
  const out: Data = {};
  for (const [field, value] of Object.entries(data)) {
    const spec = effectiveField(schema, data, field);
    if (spec.type === "array") {
      out[field] = cleanItems(spec, value, previous[field], uid, field, problems);
      continue;
    }
    const problem = fieldProblem(spec, value);
    if (problem === null) {
      out[field] = value;
      continue;
    }
    problems.set(problemKey(uid, [...prefix, field]), problem);
    const fallback = previous[field];
    if (fallback !== undefined && fieldProblem(spec, fallback) === null) out[field] = fallback;
  }
  return out;
}

function cleanBlock(block: BlockDoc, catalog: Catalog, saved: PageDocument | null, problems: Map<string, string>): BlockDoc {
  const schema = catalog.types[block.type]?.schema;
  if (!schema) return block;
  const before = saved ? locate(saved, block.uid)?.block.data ?? {} : {};
  return { ...block, data: cleanData(schema, block.data, before, block.uid, [], problems) };
}

export function draftSafe(doc: PageDocument, catalog: Catalog, saved: PageDocument | null): {
  doc: PageDocument;
  problems: Map<string, string>;
} {
  const problems = new Map<string, string>();
  const zones = Object.fromEntries(
    Object.entries(doc.zones).map(([zone, blocks]) => [zone, blocks.map((b) => cleanBlock(b, catalog, saved, problems))]),
  );
  return { doc: { ...doc, zones }, problems };
}
