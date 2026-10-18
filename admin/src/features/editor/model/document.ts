// Documento della pagina (D-38) e operazioni pure: ogni funzione restituisce un documento nuovo.
import type { Catalog, FieldSchema } from "../../../api/catalog";

export type Data = Record<string, unknown>;
export type Path = (string | number)[];

export interface BlockDoc {
  uid: string;
  type: string;
  variant: string | null;
  data: Data;
}

export interface Seo {
  title?: string;
  description?: string;
  og_image_media_id?: number;
  noindex?: boolean;
}

export interface PageDocument {
  title: string;
  layout: string;
  seo: Seo;
  zones: Record<string, BlockDoc[]>;
}

export interface Located {
  zone: string;
  index: number;
  block: BlockDoc;
}

export function locate(doc: PageDocument, uid: string): Located | null {
  for (const [zone, blocks] of Object.entries(doc.zones)) {
    const index = blocks.findIndex((block) => block.uid === uid);
    if (index >= 0) return { zone, index, block: blocks[index]! };
  }
  return null;
}

export function uids(doc: PageDocument): Set<string> {
  return new Set(Object.values(doc.zones).flatMap((blocks) => blocks.map((b) => b.uid)));
}

/** Valore nuovo dentro `target` al percorso `path`; `undefined` toglie la chiave. */
export function setPath(target: unknown, path: Path, value: unknown): unknown {
  if (path.length === 0) return value;
  const [head, ...rest] = path as [string | number, ...Path];
  if (Array.isArray(target)) {
    const copy = [...target];
    copy[Number(head)] = setPath(copy[Number(head)], rest, value);
    return copy;
  }
  const base = target && typeof target === "object" ? (target as Data) : {};
  const next = setPath(base[head], rest, value);
  if (next !== undefined) return { ...base, [head]: next };
  return Object.fromEntries(Object.entries(base).filter(([key]) => key !== String(head)));
}

export function getPath(target: unknown, path: Path): unknown {
  return path.reduce<unknown>((node, key) => {
    if (node && typeof node === "object") return (node as Record<string | number, unknown>)[key];
    return undefined;
  }, target);
}

function mapZones(doc: PageDocument, fn: (zone: string, blocks: BlockDoc[]) => BlockDoc[]): PageDocument {
  const zones = Object.fromEntries(Object.entries(doc.zones).map(([zone, blocks]) => [zone, fn(zone, blocks)]));
  return { ...doc, zones };
}

function mapBlock(doc: PageDocument, uid: string, fn: (block: BlockDoc) => BlockDoc): PageDocument {
  return mapZones(doc, (_zone, blocks) => blocks.map((block) => (block.uid === uid ? fn(block) : block)));
}

export function updateField(doc: PageDocument, uid: string, path: Path, value: unknown): PageDocument {
  return mapBlock(doc, uid, (block) => ({ ...block, data: setPath(block.data, path, value) as Data }));
}

export function setVariant(doc: PageDocument, uid: string, variant: string | null): PageDocument {
  return mapBlock(doc, uid, (block) => ({ ...block, variant }));
}

export function setTitle(doc: PageDocument, title: string): PageDocument {
  return { ...doc, title };
}

export function setSeo<K extends keyof Seo>(doc: PageDocument, key: K, value: Seo[K] | undefined): PageDocument {
  return { ...doc, seo: setPath(doc.seo, [key], value) as Seo };
}

export function addBlock(doc: PageDocument, zone: string, block: BlockDoc, index?: number): PageDocument {
  const blocks = doc.zones[zone] ?? [];
  const at = index === undefined ? blocks.length : Math.max(0, Math.min(index, blocks.length));
  return { ...doc, zones: { ...doc.zones, [zone]: [...blocks.slice(0, at), block, ...blocks.slice(at)] } };
}

export function removeBlock(doc: PageDocument, uid: string): PageDocument {
  return mapZones(doc, (_zone, blocks) => blocks.filter((block) => block.uid !== uid));
}

export function moveBlock(doc: PageDocument, uid: string, zone: string, index: number): PageDocument {
  const found = locate(doc, uid);
  if (!found) return doc;
  return addBlock(removeBlock(doc, uid), zone, found.block, index);
}

export function shiftBlock(doc: PageDocument, uid: string, delta: -1 | 1): PageDocument {
  const found = locate(doc, uid);
  if (!found) return doc;
  const target = found.index + delta;
  if (target < 0 || target >= (doc.zones[found.zone]?.length ?? 0)) return doc;
  return moveBlock(doc, uid, found.zone, target);
}

export function duplicateBlock(doc: PageDocument, uid: string, newUid: string): PageDocument {
  const found = locate(doc, uid);
  if (!found) return doc;
  const copy: BlockDoc = { ...found.block, uid: newUid, data: structuredClone(found.block.data) };
  return addBlock(doc, found.zone, copy, found.index + 1);
}

function defaults(schema: FieldSchema): Data {
  return Object.fromEntries(
    Object.entries(schema.properties ?? {})
      .filter(([, spec]) => spec.default !== undefined)
      .map(([name, spec]) => [name, spec.default]),
  );
}

export function newBlock(catalog: Catalog, type: string, uid: string): BlockDoc {
  const schema = catalog.types[type]?.schema ?? {};
  return { uid, type, variant: catalog.variants[type]?.default ?? null, data: defaults(schema) };
}

/** La zona ha ancora posto (max del tema)? */
export function hasRoom(doc: PageDocument, catalog: Catalog, zone: string): boolean {
  const spec = catalog.layouts[doc.layout]?.zones[zone];
  return spec !== undefined && (spec.max === null || (doc.zones[zone]?.length ?? 0) < spec.max);
}

/** Zone del layout che ammettono il tipo e hanno posto (per "Sposta in…"). */
export function zonesFor(doc: PageDocument, catalog: Catalog, type: string, except?: string): string[] {
  const layout = catalog.layouts[doc.layout];
  if (!layout) return [];
  return Object.entries(layout.zones)
    .filter(([name, zone]) => name !== except && zone.blocks.includes(type) && hasRoom(doc, catalog, name))
    .map(([name]) => name);
}

/** Il documento con tutte le zone del layout (vuote se mancano) e le varianti di default. */
export function normalize(doc: PageDocument, catalog: Catalog, fallbackLayout: string): PageDocument {
  const layoutName = catalog.layouts[doc.layout] ? doc.layout : fallbackLayout;
  const layout = catalog.layouts[layoutName];
  const zones: Record<string, BlockDoc[]> = {};
  for (const name of Object.keys(layout?.zones ?? {})) {
    zones[name] = (doc.zones[name] ?? []).map((block) => ({
      ...block,
      variant: block.variant ?? catalog.variants[block.type]?.default ?? null,
      data: block.data ?? {},
    }));
  }
  return { title: doc.title, layout: layoutName, seo: doc.seo ?? {}, zones };
}
