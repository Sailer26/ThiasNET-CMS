// Libreria media per l'editor (D-111): elenco, lettura per id, caricamento, testo alternativo.
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
  version: number;
  url: string;
  thumbnail_url: string | null;
}

export const PICKER_PAGE_SIZE = 24;

export interface MediaPage {
  items: Media[];
  total: number;
}

export async function listMedia(options: { kind: MediaKind; q?: string; page?: number }): Promise<MediaPage> {
  const params = new URLSearchParams({ kind: options.kind, page: String(options.page ?? 1), limit: String(PICKER_PAGE_SIZE) });
  if (options.q) params.set("q", options.q);
  const { data, meta } = await request<Media[]>("GET", `/media?${params.toString()}`);
  return { items: data, total: typeof meta.total === "number" ? meta.total : data.length };
}

export async function mediaByIds(ids: number[]): Promise<Media[]> {
  if (ids.length === 0) return [];
  return (await request<Media[]>("GET", `/media?ids=${ids.join(",")}`)).data;
}

export interface Uploaded {
  media: Media;
  duplicate: boolean;
}

export async function uploadMedia(file: File, alt: string): Promise<Uploaded> {
  const form = new FormData();
  form.append("file", file);
  if (alt.trim()) form.append("alt", alt.trim());
  const { data, meta } = await request<Media>("POST", "/media", form);
  return { media: data, duplicate: meta.duplicate === true };
}

export async function updateAlt(id: number, version: number, alt: string): Promise<Media> {
  return (await request<Media>("PATCH", `/media/${id}`, { version, alt })).data;
}
