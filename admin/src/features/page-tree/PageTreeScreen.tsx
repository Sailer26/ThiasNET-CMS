import { useCallback, useEffect, useState } from "react";
import { ApiError, errorMessage, isConflict } from "../../api/client";
import {
  createPage,
  fetchTree,
  reorderPages,
  trashPage,
  updatePage,
  type Tree,
} from "../../api/pages";
import type { PageNode } from "../../api/types";
import { Permission } from "../../session/can";
import { useSession } from "../../session/context";
import { it } from "../../text/it";
import { FormDialog } from "../../ui/FormDialog";
import { Notice, type NoticeState } from "../../ui/Notice";
import { AddressDialog, CreatePageDialog, MoveDialog } from "./dialogs";
import { PageRow, type RowAction } from "./PageRow";
import { hasHome, reordered } from "./tree";

type DialogState =
  | { kind: "create"; home: boolean }
  | { kind: "move" | "address" | "trash"; node: PageNode };

/** Errori dopo i quali l'elenco sullo schermo non è più quello vero: si ricarica (D-92). */
function isStale(error: unknown): boolean {
  return isConflict(error) || (error instanceof ApiError && error.code === "reorder_mismatch");
}

export function PageTreeScreen() {
  const { site, can, reloadKey } = useSession();
  const [tree, setTree] = useState<Tree | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const locale = site.default_locale; // D-94: solo la prima lingua fino alla Fase 7

  const reload = useCallback(
    () =>
      fetchTree(locale).then(
        (loaded) => {
          setTree(loaded);
          setLoadError(null);
        },
        (error: unknown) => setLoadError(errorMessage(error)),
      ),
    [locale],
  );

  useEffect(() => {
    void reload();
  }, [reload, reloadKey]);

  /** Esegue un'azione; con un conflitto chiude la finestra, avvisa e ricarica. */
  const act = useCallback(
    async (action: () => Promise<void>, success: string) => {
      try {
        await action();
      } catch (error) {
        if (!isStale(error)) throw error;
        setDialog(null);
        setNotice({ kind: "error", text: errorMessage(error) });
        await reload();
        return;
      }
      setDialog(null);
      setNotice({ kind: "success", text: success });
      await reload();
    },
    [reload],
  );

  function shift(node: PageNode, siblings: PageNode[], delta: -1 | 1) {
    const ids = reordered(siblings, node.id, delta);
    if (!ids) return;
    act(() => reorderPages(node.parent_id, locale, ids), it.tree.moved(node.title)).catch(
      (error: unknown) => setNotice({ kind: "error", text: errorMessage(error) }),
    );
  }

  function branch(nodes: PageNode[]) {
    return (
      <ul className="tree">
        {nodes.map((node) => {
          const handle = (action: RowAction) => {
            if (action === "up" || action === "down") shift(node, nodes, action === "up" ? -1 : 1);
            else setDialog({ kind: action, node });
          };
          return (
            <li key={node.id} className="tree__item">
              <PageRow
                node={node}
                siteUrl={site.url}
                canUp={reordered(nodes, node.id, -1) !== null}
                canDown={reordered(nodes, node.id, 1) !== null}
                canPublish={can(Permission.publish)}
                onAction={handle}
              />
              {node.children.length > 0 && branch(node.children)}
            </li>
          );
        })}
      </ul>
    );
  }

  const roots = tree?.nodes ?? [];
  const withHome = hasHome(roots);

  return (
    <section className="screen" aria-labelledby="pages-title">
      <div className="screen__head">
        <h1 id="pages-title">{it.tree.title}</h1>
        {tree && withHome && (
          <button type="button" className="button button--primary" onClick={() => setDialog({ kind: "create", home: false })}>
            {it.tree.newPage}
          </button>
        )}
      </div>
      <p className="phone-only hint">{it.tree.phoneNotice}</p>
      {notice && <Notice {...notice} onClose={() => setNotice(null)} />}
      {loadError && <Notice kind="error" text={loadError} />}
      {!tree && !loadError && <p role="status">{it.loading}</p>}
      {tree?.truncated && <Notice kind="info" text={it.tree.truncated} />}
      {tree && !withHome && (
        <div className="empty">
          <p>{it.tree.noHome}</p>
          <button type="button" className="button button--primary" onClick={() => setDialog({ kind: "create", home: true })}>
            {it.tree.createHome}
          </button>
        </div>
      )}
      {tree && roots.length > 0 && branch(roots)}

      {dialog?.kind === "create" && (
        <CreatePageDialog
          roots={roots}
          home={dialog.home}
          onClose={() => setDialog(null)}
          onCreate={(title, parentId) =>
            act(async () => {
              await createPage({
                title,
                locale,
                parent_id: parentId,
                layout: dialog.home ? site.home_layout : site.default_layout,
                ...(dialog.home ? { slug: "" } : {}),
              });
            }, it.tree.created(title))
          }
        />
      )}
      {dialog?.kind === "move" && (
        <MoveDialog
          roots={roots}
          node={dialog.node}
          onClose={() => setDialog(null)}
          onMove={(parentId) =>
            act(async () => {
              await updatePage(dialog.node.id, dialog.node.version, { parent_id: parentId });
            }, it.tree.moved(dialog.node.title))
          }
        />
      )}
      {dialog?.kind === "address" && (
        <AddressDialog
          roots={roots}
          node={dialog.node}
          onClose={() => setDialog(null)}
          onSave={(slug) =>
            act(async () => {
              await updatePage(dialog.node.id, dialog.node.version, { slug });
            }, it.tree.addressChanged(dialog.node.title))
          }
        />
      )}
      {dialog?.kind === "trash" && (
        <FormDialog
          title={it.tree.trash}
          submitLabel={it.tree.trash}
          danger
          onClose={() => setDialog(null)}
          onSubmit={() =>
            act(async () => {
              await trashPage(dialog.node.id, dialog.node.version);
            }, it.tree.trashed(dialog.node.title))
          }
        >
          <p>{it.tree.trashConfirm(dialog.node.title)}</p>
        </FormDialog>
      )}
    </section>
  );
}
