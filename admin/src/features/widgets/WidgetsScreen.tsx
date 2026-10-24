import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../../api/client";
import { fetchTree } from "../../api/pages";
import type { PageNode } from "../../api/types";
import { fetchWidgetAreas, type WidgetAreaInfo } from "../../api/widgets";
import { useSession } from "../../session/context";
import { wg } from "../../text/widgets";
import type { PageOption } from "../menus/MenuEditor";
import { AreaEditor } from "./AreaEditor";

function flatten(nodes: PageNode[], depth = 0): PageOption[] {
  return nodes.flatMap((node) => [{ id: node.id, title: node.title, path: node.path, depth }, ...flatten(node.children, depth + 1)]);
}

/** Widget (6c, D-140, D-142): una scheda per ogni parte del sito prevista dal tema. */
export function WidgetsScreen() {
  const { site } = useSession();
  const [areas, setAreas] = useState<WidgetAreaInfo[] | null>(null);
  const [pages, setPages] = useState<PageOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const latest = useRef(0);

  /** Pagine nella lingua delle aree (il server controlla quelle). Conta solo l'ultima richiesta. */
  const load = useCallback(() => {
    const request = ++latest.current;
    fetchWidgetAreas()
      .then(async (found) => [found, await fetchTree(found[0]?.locale ?? site.default_locale)] as const)
      .then(
        ([found, tree]) => {
          if (request !== latest.current) return;
          setAreas(found);
          setPages(flatten(tree.nodes));
          setError(null);
        },
        (failure: unknown) => {
          if (request === latest.current) setError(errorMessage(failure));
        },
      );
  }, [site.default_locale]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <section className="screen" aria-labelledby="widgets-title">
      <div className="screen__head">
        <h1 id="widgets-title" tabIndex={-1}>
          {wg.title}
        </h1>
      </div>
      <p className="hint">{wg.intro}</p>
      {error && (
        <p className="notice notice--error" role="alert">
          {error}
        </p>
      )}
      {!areas && !error && <p role="status">{wg.loading}</p>}
      {areas?.map((area) => (
        // key con la versione: dopo "Ricarica" la scheda riparte dal server
        <AreaEditor key={`${area.area}-${area.version}`} area={area} pages={pages} onReload={load} />
      ))}
    </section>
  );
}
