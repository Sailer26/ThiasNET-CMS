// Cambio del tipo di pagina (D-110): i blocchi seguono la zona con lo stesso nome, poi la prima
// che li ammette e ha posto; quelli senza posto si elencano (la conferma decide).
import type { Catalog } from "../../../api/catalog";
import type { BlockDoc, PageDocument } from "./document";

export interface Relayout {
  doc: PageDocument;
  dropped: BlockDoc[];
}

export function relayout(doc: PageDocument, catalog: Catalog, layoutName: string): Relayout {
  const layout = catalog.layouts[layoutName];
  if (!layout) return { doc, dropped: [] };
  const zones: Record<string, BlockDoc[]> = Object.fromEntries(Object.keys(layout.zones).map((name) => [name, []]));
  const fits = (name: string, block: BlockDoc) => {
    const zone = layout.zones[name];
    return zone !== undefined && zone.blocks.includes(block.type) && (zone.max === null || zones[name]!.length < zone.max);
  };
  const dropped: BlockDoc[] = [];
  for (const [from, blocks] of Object.entries(doc.zones)) {
    for (const block of blocks) {
      const target = fits(from, block) ? from : Object.keys(layout.zones).find((name) => fits(name, block));
      if (target === undefined) dropped.push(block);
      else zones[target]!.push(block);
    }
  }
  return { doc: { ...doc, layout: layoutName, zones }, dropped };
}
