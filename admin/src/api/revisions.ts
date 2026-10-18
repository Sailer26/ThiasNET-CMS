// Versioni e programmazione di una pagina (D-40, D-42, D-47, D-121, D-122).
import type { PageDocument } from "../features/editor/model/document";
import { request } from "./client";
import type { Page } from "./types";

export type RevisionKind = "published" | "scheduled" | "unpublished" | "draft";

export interface Revision {
  id: number;
  kind: RevisionKind;
  author_name: string;
  title: string;
  created_at: string;
}

export const REVISIONS_PAGE_SIZE = 50;

export async function listRevisions(pageId: number): Promise<Revision[]> {
  return (await request<Revision[]>("GET", `/pages/${pageId}/revisions?page=1&limit=${REVISIONS_PAGE_SIZE}`)).data;
}

export async function getRevision(pageId: number, id: number): Promise<PageDocument> {
  return (await request<Revision & { snapshot: PageDocument }>("GET", `/pages/${pageId}/revisions/${id}`)).data.snapshot;
}

/** La versione torna nella bozza (mai online, D-42); restituisce la nuova versione della bozza. */
export async function restoreRevision(pageId: number, id: number, draftVersion: number): Promise<number> {
  const { data } = await request<{ version: number }>("POST", `/pages/${pageId}/revisions/${id}/restore`, {
    draft_version: draftVersion,
  });
  return data.version;
}

export async function schedulePage(pageId: number, draftVersion: number, publishAt: string): Promise<Page> {
  return (await request<Page>("POST", `/pages/${pageId}/schedule`, { draft_version: draftVersion, publish_at: publishAt })).data;
}

export async function unschedulePage(pageId: number, version: number): Promise<Page> {
  return (await request<Page>("DELETE", `/pages/${pageId}/schedule`, { version })).data;
}
