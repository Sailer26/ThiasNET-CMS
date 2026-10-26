// Notizie e altre raccolte del tema (7a, 7b): elenco, bozza, pubblicazione, versioni.
import type { FieldSchema } from "./catalog";
import type { CheckItem, Checks } from "./drafts";
import type { Revision } from "./revisions";
import { localized, request } from "./client";
import type { Seo } from "../features/editor/model/document";

export type EntryStatus = "draft" | "published" | "scheduled";

export interface EntryDocument {
  title: string;
  fields: Record<string, unknown>;
  seo: Seo;
}

export interface Entry {
  id: number;
  collection: string;
  locale: string;
  slug: string;
  title: string;
  status: EntryStatus;
  version: number;
  publish_at: string | null;
  published_at: string | null;
  sort_at: string | null;
  updated_at: string | null;
  has_draft: boolean;
  url: string | null;
  schedule: { publish_at: string; author_name: string; draft_newer: boolean } | null;
}

export interface CollectionInfo {
  key: string;
  label: string;
  per_page: number;
  schema: FieldSchema;
  listing: { page_id: number; path: string } | null;
}

export interface EntryDraft {
  version: number;
  data: EntryDocument;
  from_published: boolean;
}

export interface EntryPage {
  items: Entry[];
  total: number;
  pages: number;
}

export const ENTRIES_PAGE_SIZE = 50;
const one = (id: number) => `/entries/${id}`;
const many = (collection: string) => `/collections/${encodeURIComponent(collection)}/entries`;

/** Le raccolte, ognuna con la sua pagina elenco (`listing`) nella lingua chiesta (D-149). */
export async function fetchCollections(locale: string): Promise<CollectionInfo[]> {
  return (await request<CollectionInfo[]>("GET", localized("/collections", locale))).data;
}

export async function fetchEntries(collection: string, page: number, trash: boolean, locale: string): Promise<EntryPage> {
  const query = `page=${page}&limit=${ENTRIES_PAGE_SIZE}${trash ? "&trash=1" : ""}`;
  const { data, meta } = await request<Entry[]>("GET", localized(`${many(collection)}?${query}`, locale));
  return { items: data, total: Number(meta.total ?? data.length), pages: Number(meta.pages ?? 1) };
}

export async function createEntry(collection: string, title: string, locale: string): Promise<Entry> {
  return (await request<Entry>("POST", many(collection), { title, locale })).data;
}

export async function fetchEntry(id: number): Promise<Entry> {
  return (await request<Entry>("GET", one(id))).data;
}

export async function changeSlug(id: number, version: number, slug: string): Promise<Entry> {
  return (await request<Entry>("PATCH", one(id), { version, slug })).data;
}

export async function trashEntry(id: number, version: number): Promise<Entry> {
  return (await request<Entry>("DELETE", one(id), { version })).data;
}

export async function restoreEntry(id: number, version: number): Promise<Entry> {
  return (await request<Entry>("POST", `${one(id)}/restore`, { version })).data;
}

export async function fetchEntryDraft(id: number): Promise<EntryDraft> {
  return (await request<EntryDraft>("GET", `${one(id)}/draft`)).data;
}

export async function saveEntryDraft(id: number, version: number, doc: EntryDocument): Promise<number> {
  return (await request<{ version: number }>("PUT", `${one(id)}/draft`, { version, ...doc })).data.version;
}

export async function discardEntryDraft(id: number, version: number): Promise<EntryDraft> {
  return (await request<EntryDraft>("DELETE", `${one(id)}/draft`, { version })).data;
}

export async function publishEntry(id: number, draftVersion: number): Promise<Entry> {
  return (await request<Entry>("POST", `${one(id)}/publish`, { draft_version: draftVersion })).data;
}

export async function scheduleEntry(id: number, draftVersion: number, publishAt: string): Promise<Entry> {
  return (await request<Entry>("POST", `${one(id)}/schedule`, { draft_version: draftVersion, publish_at: publishAt })).data;
}

export async function unscheduleEntry(id: number, version: number): Promise<Entry> {
  return (await request<Entry>("POST", `${one(id)}/unschedule`, { version })).data;
}

export async function unpublishEntry(id: number, version: number): Promise<Entry> {
  return (await request<Entry>("POST", `${one(id)}/unpublish`, { version })).data;
}

function isItems(value: unknown): value is CheckItem[] {
  return Array.isArray(value) && value.every((item) => typeof (item as CheckItem | null)?.message === "string");
}

export async function fetchEntryChecks(id: number): Promise<Checks> {
  const { data } = await request<unknown>("GET", `${one(id)}/checks`);
  const found = (data ?? {}) as Partial<Record<keyof Checks, unknown>>;
  if (!isItems(found.blocking) || !isItems(found.warnings)) throw new Error("risposta del controllo non valida");
  return { blocking: found.blocking, warnings: found.warnings };
}

export async function listEntryRevisions(id: number): Promise<Revision[]> {
  return (await request<Revision[]>("GET", `${one(id)}/revisions`)).data;
}

export async function getEntryRevision(id: number, revisionId: number): Promise<EntryDocument> {
  return (await request<Revision & { snapshot: EntryDocument }>("GET", `${one(id)}/revisions/${revisionId}`)).data.snapshot;
}

export async function restoreEntryRevision(id: number, revisionId: number, draftVersion: number): Promise<number> {
  const { data } = await request<{ version: number }>("POST", `${one(id)}/revisions/${revisionId}/restore`, {
    draft_version: draftVersion,
  });
  return data.version;
}
