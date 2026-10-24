// Widget per area (D-140, D-142, D-146): la lista intera di un'area si salva con la versione.
import type { FieldSchema } from "./catalog";
import { request } from "./client";

export type VisibilityMode = "all" | "only" | "except";

export interface Visibility {
  mode: VisibilityMode;
  pages: number[];
}

export interface WidgetItem {
  uid: string;
  type: string;
  data: Record<string, unknown>;
  visibility?: Visibility;
  /** Solo il banner: ISO con il fuso; dopo quell'ora sparisce dal sito. */
  until?: string | null;
}

export interface WidgetType {
  type: string;
  label: string;
  schema: FieldSchema;
}

export interface WidgetAreaInfo {
  area: string;
  label: string;
  /** Lingua dell'area: le pagine della visibilità si scelgono in questa lingua. */
  locale: string;
  types: WidgetType[];
  version: number;
  items: WidgetItem[];
}

const areaPath = (area: string) => `/widgets/${encodeURIComponent(area)}`;

export async function fetchWidgetAreas(): Promise<WidgetAreaInfo[]> {
  return (await request<WidgetAreaInfo[]>("GET", "/widgets")).data;
}

export async function fetchWidgetArea(area: string): Promise<WidgetAreaInfo> {
  return (await request<WidgetAreaInfo>("GET", areaPath(area))).data;
}

export async function storeWidgetArea(area: string, version: number, items: WidgetItem[]): Promise<WidgetAreaInfo> {
  return (await request<WidgetAreaInfo>("PUT", areaPath(area), { version, items })).data;
}
