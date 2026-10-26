// Caricamento dell'editor: pagina, bozza (o pubblicato) e catalogo in parallelo, poi le pagine
// della lingua della pagina (D-159: l'editor lavora sempre nella lingua della sua pagina).
import { useCallback, useEffect, useRef, useState } from "react";
import { fetchCatalog, type Catalog } from "../../api/catalog";
import { errorMessage } from "../../api/client";
import { fetchDraft, fetchPage, type Draft } from "../../api/drafts";
import { fetchTree } from "../../api/pages";
import type { Page, PageNode } from "../../api/types";
import { normalize } from "./model/document";

export interface Loaded {
  page: Page;
  draft: Draft;
  catalog: Catalog;
  pages: string[];
}

export type LoadState = { kind: "loading" } | { kind: "failed"; message: string } | { kind: "ready"; data: Loaded };

function paths(nodes: PageNode[]): string[] {
  return nodes.flatMap((node) => [node.path, ...paths(node.children)]);
}

export function useEditorData(pageId: number, fallbackLayout: string) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const latest = useRef(0);

  const load = useCallback(() => {
    const request = ++latest.current;
    return Promise.all([fetchPage(pageId), fetchDraft(pageId), fetchCatalog()])
      .then(async ([page, draft, catalog]) => [page, draft, catalog, await fetchTree(page.locale)] as const)
      .then(
      ([page, draft, catalog, tree]) => {
        if (request !== latest.current) return;
        const data = normalize(draft.data, catalog, fallbackLayout);
        setState({ kind: "ready", data: { page, draft: { ...draft, data }, catalog, pages: paths(tree.nodes) } });
      },
      (error: unknown) => {
        if (request === latest.current) setState({ kind: "failed", message: errorMessage(error) });
      },
    );
  }, [pageId, fallbackLayout]);

  useEffect(() => {
    void load();
  }, [load]);

  return { state, reload: load };
}
