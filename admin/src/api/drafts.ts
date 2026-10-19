// Bozza e pubblicazione di una pagina (D-38, D-103, D-113).
import type { PageDocument } from "../features/editor/model/document";
import { request } from "./client";
import type { Page } from "./types";

export interface Draft {
  version: number;
  data: PageDocument;
  from_published: boolean;
  updated_at: string | null;
}

export async function fetchPage(id: number): Promise<Page> {
  return (await request<Page>("GET", `/pages/${id}`)).data;
}

export async function fetchDraft(id: number): Promise<Draft> {
  return (await request<Draft>("GET", `/pages/${id}/draft`)).data;
}

/** Salva il documento intero; restituisce la nuova versione della bozza. */
export async function saveDraft(id: number, version: number, doc: PageDocument): Promise<number> {
  const { data } = await request<{ version: number }>("PUT", `/pages/${id}/draft`, {
    version,
    ...doc,
  });
  return data.version;
}

export async function discardDraft(id: number, version: number): Promise<void> {
  await request("DELETE", `/pages/${id}/draft`, { version });
}

export interface CheckItem {
  path: string;
  code: string;
  message: string;
}

export interface Checks {
  blocking: CheckItem[];
  warnings: CheckItem[];
}

function isItems(value: unknown): value is CheckItem[] {
  return Array.isArray(value) && value.every((item) => item !== null && typeof item === "object" && typeof (item as CheckItem).path === "string");
}

/** Controllo prima di pubblicare (D-135): bloccanti come la pubblicazione, avvisi che non bloccano. */
export async function fetchChecks(id: number): Promise<Checks> {
  const { data } = await request<unknown>("GET", `/pages/${id}/checks`);
  const found = (data ?? {}) as Partial<Record<keyof Checks, unknown>>;
  if (!isItems(found.blocking) || !isItems(found.warnings)) throw new Error("risposta del controllo non valida");
  return { blocking: found.blocking, warnings: found.warnings };
}

export async function publishPage(id: number, draftVersion: number): Promise<Page> {
  return (await request<Page>("POST", `/pages/${id}/publish`, { draft_version: draftVersion })).data;
}

export async function unpublishPage(id: number, version: number): Promise<Page> {
  return (await request<Page>("POST", `/pages/${id}/unpublish`, { version })).data;
}
