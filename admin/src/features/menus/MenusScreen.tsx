import { useCallback, useEffect, useState } from "react";
import { fetchMenus, type MenuInfo } from "../../api/menus";
import { errorMessage } from "../../api/client";
import { fetchTree } from "../../api/pages";
import type { PageNode } from "../../api/types";
import { usePanelLocale } from "../../session/localeContext";
import { mn } from "../../text/menus";
import { MenuEditor, type PageOption } from "./MenuEditor";

function flatten(nodes: PageNode[], depth = 0): PageOption[] {
  return nodes.flatMap((node) => [
    { id: node.id, title: node.title, path: node.path, depth },
    ...flatten(node.children, depth + 1),
  ]);
}

/** Menu del sito (6b, D-140, D-141): uno per posizione prevista dal tema. */
export function MenusScreen() {
  const { locale } = usePanelLocale(); // D-159
  const [menus, setMenus] = useState<MenuInfo[] | null>(null);
  const [pages, setPages] = useState<PageOption[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([fetchMenus(locale), fetchTree(locale)]).then(
      ([found, tree]) => {
        setMenus(found);
        setPages(flatten(tree.nodes));
        setError(null);
      },
      (failure: unknown) => setError(errorMessage(failure)),
    );
  }, [locale]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <section className="screen" aria-labelledby="menus-title">
      <div className="screen__head">
        <h1 id="menus-title" tabIndex={-1}>
          {mn.title}
        </h1>
      </div>
      {error && (
        <p className="notice notice--error" role="alert">
          {error}
        </p>
      )}
      {!menus && !error && <p role="status">{mn.loading}</p>}
      {menus?.map((menu) => (
        // key con la versione: dopo "Ricarica" l'editor riparte dal server
        <MenuEditor key={`${menu.locale}-${menu.location}-${menu.version}-${menu.manual}`} menu={menu} pages={pages} onReload={load} />
      ))}
    </section>
  );
}
