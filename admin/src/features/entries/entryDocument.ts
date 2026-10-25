// Il documento di una notizia nel pannello (7b): operazioni pure, sempre un oggetto nuovo.
import type { FieldSchema } from "../../api/catalog";
import type { EntryDocument } from "../../api/entries";
import type { Seo } from "../editor/model/document";
import { commit, redo, startHistory, undo, type History } from "../editor/model/history";
import { fieldProblem } from "../editor/schema/validate";

export function setField(doc: EntryDocument, name: string, value: unknown): EntryDocument {
  const fields = { ...doc.fields };
  if (value === undefined) delete fields[name];
  else fields[name] = value;
  return { ...doc, fields };
}

export function setTitle(doc: EntryDocument, title: string): EntryDocument {
  return { ...doc, title };
}

export function setSeo<K extends keyof Seo>(doc: EntryDocument, key: K, value: Seo[K] | undefined): EntryDocument {
  const seo = { ...doc.seo };
  if (value === undefined) delete seo[key];
  else seo[key] = value;
  return { ...doc, seo };
}

/** D-104: un campo scritto a metà non fa fallire il salvataggio: va l'ultimo valore valido
 * (o niente). I campi che il tema non ha più restano fuori (il server li rifiuterebbe). */
export function entrySafe(
  doc: EntryDocument,
  schema: FieldSchema,
  saved: EntryDocument | null,
): { doc: EntryDocument; problems: Map<string, string> } {
  const problems = new Map<string, string>();
  const fields: Record<string, unknown> = {};
  for (const [name, value] of Object.entries(doc.fields)) {
    const spec = schema.properties?.[name];
    if (!spec) continue;
    const problem = fieldProblem(spec, value);
    if (problem === null) {
      fields[name] = value;
      continue;
    }
    problems.set(name, problem);
    const before = saved?.fields[name];
    if (before !== undefined && fieldProblem(spec, before) === null) fields[name] = before;
  }
  return { doc: { ...doc, fields }, problems };
}

/** I media del documento: i campi immagine e l'immagine per i social. */
export function mediaIdsOf(doc: EntryDocument, schema: FieldSchema): number[] {
  const ids = Object.entries(schema.properties ?? {})
    .filter(([, spec]) => spec["x-media"])
    .map(([name]) => doc.fields[name])
    .filter((value): value is number => typeof value === "number");
  const og = doc.seo.og_image_media_id;
  return typeof og === "number" ? [...ids, og] : ids;
}

/** Il primo campo del tipo cercato (per il telefono: data di oggi, testo, foto). */
export function firstField(schema: FieldSchema, test: (spec: FieldSchema) => boolean): string | null {
  return Object.entries(schema.properties ?? {}).find(([, spec]) => test(spec))?.[0] ?? null;
}

export type HistoryAction =
  | { type: "edit"; fn: (doc: EntryDocument) => EntryDocument; key: string | null; at: number }
  | { type: "undo" }
  | { type: "redo" }
  | { type: "replace"; doc: EntryDocument };

/** Annulla e ripristina (D-105) con la stessa storia delle pagine. */
export function historyReducer(state: History<EntryDocument>, action: HistoryAction): History<EntryDocument> {
  switch (action.type) {
    case "edit":
      return commit(state, action.fn(state.present), action.key, action.at);
    case "undo":
      return undo(state);
    case "redo":
      return redo(state);
    case "replace":
      return startHistory(action.doc);
  }
}
