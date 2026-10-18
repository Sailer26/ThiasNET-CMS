// Libreria media (D-70 … D-85, D-111, D-117 … D-120).
import { request } from "./client";

export type MediaKind = "image" | "document";

export interface Media {
  id: number;
  kind: MediaKind;
  name: string;
  ext: string;
  alt: string;
  width: number | null;
  height: number | null;
  size_bytes?: number;
  focal_x?: number;
  focal_y?: number;
  folder_id?: number | null;
  version: number;
  url: string;
  thumbnail_url: string | null;
  created_at?: string;
}

export interface MediaUse {
  page_id: number;
  title: string;
  path: string;
  where: string;
}

export interface MediaDetail extends Media {
  used_by: MediaUse[];
}

export interface Folder {
  id: number;
  name: string;
  parent_id: number | null;
  count: number;
  children: Folder[];
}

export interface Usage {
  used_bytes: number;
  quota_bytes: number;
  max_upload_bytes: number;
  count: number;
}

export const PICKER_PAGE_SIZE = 24;
const IDS_PER_REQUEST = 100; // tetto del server (app/api/admin/media.py, MAX_IDS)

export interface MediaPage {
  items: Media[];
  total: number;
}

export interface MediaQuery {
  kind?: MediaKind | undefined;
  q?: string | undefined;
  page?: number | undefined;
  /** id di una cartella, "none" per i file senza cartella, assente per tutti. */
  folder?: number | "none" | undefined;
  missingAlt?: boolean | undefined;
}

export async function listMedia(query: MediaQuery): Promise<MediaPage> {
  const params = new URLSearchParams({ page: String(query.page ?? 1), limit: String(PICKER_PAGE_SIZE) });
  if (query.kind) params.set("kind", query.kind);
  if (query.q) params.set("q", query.q);
  if (query.folder !== undefined) params.set("folder_id", String(query.folder));
  if (query.missingAlt) params.set("missing_alt", "1");
  const { data, meta } = await request<Media[]>("GET", `/media?${params.toString()}`);
  return { items: data, total: typeof meta.total === "number" ? meta.total : data.length };
}

export async function mediaByIds(ids: number[]): Promise<Media[]> {
  const found: Media[] = [];
  for (let start = 0; start < ids.length; start += IDS_PER_REQUEST) {
    const batch = ids.slice(start, start + IDS_PER_REQUEST);
    found.push(...(await request<Media[]>("GET", `/media?ids=${batch.join(",")}`)).data);
  }
  return found;
}

export async function getMedia(id: number): Promise<MediaDetail> {
  return (await request<MediaDetail>("GET", `/media/${id}`)).data;
}

export interface Uploaded {
  media: Media;
  duplicate: boolean;
}

export async function uploadMedia(file: File, alt: string, folderId?: number | null): Promise<Uploaded> {
  const form = new FormData();
  form.append("file", file);
  if (alt.trim()) form.append("alt", alt.trim());
  if (folderId) form.append("folder_id", String(folderId));
  const { data, meta } = await request<Media>("POST", "/media", form);
  return { media: data, duplicate: meta.duplicate === true };
}

export async function updateAlt(id: number, version: number, alt: string): Promise<Media> {
  return updateMedia(id, version, { alt });
}

export async function updateMedia(
  id: number,
  version: number,
  changes: { name?: string; alt?: string; focal_x?: number; focal_y?: number; folder_id?: number | null },
): Promise<Media> {
  return (await request<Media>("PATCH", `/media/${id}`, { version, ...changes })).data;
}

export async function replaceFile(id: number, version: number, file: File): Promise<Media> {
  const form = new FormData();
  form.append("file", file);
  form.append("version", String(version));
  return (await request<Media>("POST", `/media/${id}/file`, form)).data;
}

export async function deleteMedia(id: number, version: number): Promise<void> {
  await request("DELETE", `/media/${id}`, { version });
}

export async function fetchUsage(): Promise<Usage> {
  return (await request<Usage>("GET", "/media/usage")).data;
}

export async function fetchFolders(): Promise<Folder[]> {
  return (await request<Folder[]>("GET", "/media/folders")).data;
}

export async function createFolder(name: string, parentId: number | null): Promise<void> {
  await request("POST", "/media/folders", { name, parent_id: parentId });
}

export async function updateFolder(id: number, changes: { name?: string; parent_id?: number | null }): Promise<void> {
  await request("PATCH", `/media/folders/${id}`, changes);
}

export async function deleteFolder(id: number): Promise<void> {
  await request("DELETE", `/media/folders/${id}`);
}
