import { request } from "./client";
import type { Page, PageNode } from "./types";

export interface Tree {
  nodes: PageNode[];
  truncated: boolean;
}

export interface NewPage {
  title: string;
  layout: string;
  locale: string;
  parent_id: number | null;
  slug?: string;
}

export const TRASH_PAGE_SIZE = 50;

export async function fetchTree(locale: string): Promise<Tree> {
  const { data, meta } = await request<PageNode[]>(
    "GET",
    `/pages/tree?locale=${encodeURIComponent(locale)}`,
  );
  return { nodes: data, truncated: meta.truncated === true };
}

export async function createPage(page: NewPage): Promise<Page> {
  return (await request<Page>("POST", "/pages", page)).data;
}

export async function updatePage(
  id: number,
  version: number,
  changes: { slug?: string; parent_id?: number | null },
): Promise<Page> {
  return (await request<Page>("PATCH", `/pages/${id}`, { version, ...changes })).data;
}

export async function reorderPages(
  parentId: number | null,
  locale: string,
  ids: number[],
): Promise<void> {
  await request("POST", "/pages/reorder", { parent_id: parentId, locale, ids });
}

export async function trashPage(id: number, version: number): Promise<Page> {
  return (await request<Page>("DELETE", `/pages/${id}`, { version })).data;
}

export async function fetchTrash(): Promise<Page[]> {
  return (await request<Page[]>("GET", `/pages/trash?page=1&limit=${TRASH_PAGE_SIZE}`)).data;
}

export async function restorePage(id: number, version: number): Promise<Page> {
  return (await request<Page>("POST", `/pages/${id}/restore`, { version })).data;
}
