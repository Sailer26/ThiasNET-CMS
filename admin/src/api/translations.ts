// Traduzioni collegate (7c, D-151): una per lingua, nello stesso gruppo.
import { request } from "./client";

export type TranslationKind = "page" | "entry";

export interface Translation {
  locale: string;
  label: string;
  id: number | null;
  title: string | null;
  status: string | null;
}

const base = (kind: TranslationKind, id: number) => `/${kind === "page" ? "pages" : "entries"}/${id}/translations`;

export async function fetchTranslations(kind: TranslationKind, id: number): Promise<Translation[]> {
  return (await request<Translation[]>("GET", base(kind, id))).data;
}

/** Crea la traduzione come copia della bozza (409 se quella lingua ce l'ha già). */
export async function translate(kind: TranslationKind, id: number, locale: string): Promise<{ id: number; locale: string }> {
  return (await request<{ id: number; locale: string }>("POST", base(kind, id), { locale })).data;
}
