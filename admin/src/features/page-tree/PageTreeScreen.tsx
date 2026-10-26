import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, errorMessage } from "../../api/client";
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
import { usePanelLocale } from "../../session/localeContext";
import { translate } from "../../api/translations";
import { languageName } from "../../text/languages";
import { it } from "../../text/it";
import { en } from "../../text/entries";
import { wg } from "../../text/widgets";
import { FormDialog } from "../../ui/FormDialog";
import { NoticeArea, type NoticeState } from "../../ui/Notice";
import { AddressDialog, CreatePageDialog, MoveDialog } from "./dialogs";
import { PageRow, type RowAction } from "./PageRow";
import { PhoneNews } from "../entries/PhoneNews";
import { PhoneNotice } from "../widgets/PhoneNotice";
import { PhonePublish } from "./PhonePublish";
import { hasHome, reordered } from "./tree";

type DialogState =
  | { kind: "create"; home: boolean }
  | { kind: "notice" }
  | { kind: "news" }
  | { kind: "move" | "address" | "trash" | "publish"; node: PageNode };

/** Errori che dicono: l'albero sullo schermo non è più quello vero. Si avvisa e si ricarica (D-92). */
const STALE_CODES = new Set([
  "version_conflict",
  "reorder_mismatch",
  "not_found",
  "parent_trashed",
  "has_children",
  "home_exists",
  "home_has_no_children",
  "cycle",
  "too_deep",
]);

function isStale(error: unknown): boolean {
  return error instanceof ApiError && STALE_CODES.has(error.code);
}

/** Il sito non ha ancora una homepage principale da tradurre: se ne crea una vuota. */
class MissingHome extends Error {}

export function PageTreeScreen() {
  const { site, can, reloadKey } = useSession();
  const [loaded, setLoaded] = useState<{ locale: string; tree: Tree } | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const latest = useRef(0);
  const { locale } = usePanelLocale(); // D-159
  const language = languageName(locale);
  // Un albero di un'altra lingua non si mostra (né si sposta) mentre arriva quello nuovo.
  const tree = loaded?.locale === locale ? loaded.tree : null;

  /** Solo la risposta dell'ultima richiesta conta: una vecchia non sovrascrive una nuova. */
  const reload = useCallback(() => {
    const request = ++latest.current;
    return fetchTree(locale).then(
      (loaded) => {
        if (request !== latest.current) return;
        setLoaded({ locale, tree: loaded });
        setLoadError(null);
      },
      (error: unknown) => {
        if (request === latest.current) setLoadError(errorMessage(error));
      },
    );
  }, [locale]);

  useEffect(() => {
    void reload();
  }, [reload, reloadKey]);

  /** Una modifica alla volta: finché non è finita (ricarica compresa) l'albero è bloccato. */
  const act = useCallback(
    async (action: () => Promise<void>, success: string, fromDialog: boolean) => {
      busyRef.current = true;
      setBusy(true);
      try {
        try {
          await action();
        } catch (error) {
          if (!isStale(error)) throw error;
          if (fromDialog) setDialog(null);
          setNotice({ kind: "error", text: errorMessage(error) });
          await reload();
          return;
        }
        if (fromDialog) setDialog(null);
        setNotice({ kind: "success", text: success });
        await reload();
      } finally {
        busyRef.current = false;
        setBusy(false);
      }
    },
    [reload],
  );

  function shift(node: PageNode, siblings: PageNode[], delta: -1 | 1) {
    const ids = reordered(siblings, node.id, delta);
    if (!ids || busyRef.current) return;
    act(() => reorderPages(node.parent_id, locale, ids), it.tree.moved(node.title), false).catch(
      (error: unknown) => setNotice({ kind: "error", text: errorMessage(error) }),
    );
  }

  const roots = tree?.nodes ?? [];
  const withHome = hasHome(roots);
  // Albero incompleto (moltissime pagine): le sorelle mostrate potrebbero non essere tutte.
  const locked = busy || tree?.truncated === true;

  function handle(action: RowAction, node: PageNode, siblings: PageNode[]) {
    if (action === "up" || action === "down") shift(node, siblings, action === "up" ? -1 : 1);
    else if (action === "trash-blocked") setNotice({ kind: "info", text: it.tree.trashNeedsPublish });
    else setDialog({ kind: action, node });
  }

  function branch(nodes: PageNode[]) {
    return (
      <ul className="tree">
        {nodes.map((node) => (
          <li key={node.id} className="tree__item">
            <PageRow
              node={node}
              siteUrl={site.url}
              canUp={reordered(nodes, node.id, -1) !== null}
              canDown={reordered(nodes, node.id, 1) !== null}
              canPublish={can(Permission.publish)}
              locked={locked}
              onAction={(action) => handle(action, node, nodes)}
            />
            {node.children.length > 0 && branch(node.children)}
          </li>
        ))}
      </ul>
    );
  }

  /** La homepage di un'altra lingua nasce come traduzione di quella principale (D-151);
   * se il sito non ne ha ancora una, si crea vuota. */
  async function homeIn() {
    if (busyRef.current) return;
    const target = locale; // la lingua di quando si è premuto
    try {
      await act(
        async () => {
          const main = (await fetchTree(site.default_locale)).nodes.find((node) => node.is_home);
          if (!main) throw new MissingHome();
          await translate("page", main.id, target);
        },
        it.tree.homeCreatedIn(languageName(target)),
        false,
      );
    } catch (error) {
      if (error instanceof MissingHome) {
        setDialog({ kind: "create", home: true });
        return;
      }
      setNotice({ kind: "error", text: errorMessage(error) });
      void reload(); // es. 409: nel frattempo qualcuno l'ha già creata
    }
  }

  return (
    <section className="screen" aria-labelledby="pages-title" data-tour="pages">
      <div className="screen__head">
        <h1 id="pages-title" tabIndex={-1}>
          {it.tree.title}
        </h1>
        {tree && withHome && (
          <button
            type="button"
            className="button button--primary"
            disabled={busy}
            onClick={() => setDialog({ kind: "create", home: false })}
          >
            {it.tree.newPage}
          </button>
        )}
      </div>
      <p className="phone-only hint">{it.tree.phoneNotice}</p>
      {(can(Permission.publish) || site.collections.length > 0) && (
        <p className="phone-only phone-actions">
          {can(Permission.publish) && (
            <button type="button" className="button" onClick={() => setDialog({ kind: "notice" })}>
              {wg.phone.open}
            </button>
          )}
          {site.collections.length > 0 && (
            <button type="button" className="button" onClick={() => setDialog({ kind: "news" })}>
              {en.phone.open}
            </button>
          )}
        </p>
      )}
      <NoticeArea notice={notice} onClose={() => setNotice(null)} />
      {loadError && (
        <div className="notice notice--error" role="alert">
          <p>{loadError}</p>
          <button type="button" className="button button--small" onClick={() => void reload()}>
            {it.retry}
          </button>
        </div>
      )}
      {!tree && !loadError && <p role="status">{it.loading}</p>}
      {tree?.truncated && <p className="notice notice--info">{it.tree.truncated}</p>}
      {tree && !withHome && !tree.truncated && locale !== site.default_locale && (
        <div className="empty">
          <p>{it.tree.noHomeIn(language)}</p>
          <button type="button" className="button button--primary" disabled={busy} onClick={() => void homeIn()}>
            {it.tree.createHomeIn(language)}
          </button>
        </div>
      )}
      {tree && !withHome && !tree.truncated && locale === site.default_locale && (
        <div className="empty">
          <p>{it.tree.noHome}</p>
          <button
            type="button"
            className="button button--primary"
            disabled={busy}
            onClick={() => setDialog({ kind: "create", home: true })}
          >
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
            act(
              async () => {
                await createPage({
                  title,
                  locale,
                  parent_id: parentId,
                  layout: dialog.home ? site.home_layout : site.default_layout,
                  ...(dialog.home ? { slug: "" } : {}),
                });
              },
              it.tree.created(title),
              true,
            )
          }
        />
      )}
      {dialog?.kind === "move" && (
        <MoveDialog
          roots={roots}
          node={dialog.node}
          onClose={() => setDialog(null)}
          onMove={(parentId) =>
            act(
              async () => {
                await updatePage(dialog.node.id, dialog.node.version, { parent_id: parentId });
              },
              it.tree.moved(dialog.node.title),
              true,
            )
          }
        />
      )}
      {dialog?.kind === "address" && (
        <AddressDialog
          roots={roots}
          node={dialog.node}
          onClose={() => setDialog(null)}
          onSave={(slug) =>
            act(
              async () => {
                await updatePage(dialog.node.id, dialog.node.version, { slug });
              },
              it.tree.addressChanged(dialog.node.title),
              true,
            )
          }
        />
      )}
      {dialog?.kind === "news" && (
        <PhoneNews
          onClose={() => setDialog(null)}
          onDone={(text) => {
            setDialog(null);
            setNotice({ kind: "success", text });
          }}
        />
      )}
      {dialog?.kind === "notice" && (
        <PhoneNotice
          onClose={() => setDialog(null)}
          onDone={(text) => {
            setDialog(null);
            setNotice({ kind: "success", text });
          }}
        />
      )}
      {dialog?.kind === "publish" && (
        <PhonePublish
          node={dialog.node}
          onClose={() => setDialog(null)}
          onDone={(text) => {
            setDialog(null);
            setNotice({ kind: "success", text });
            void reload();
          }}
        />
      )}
      {dialog?.kind === "trash" && (
        <FormDialog
          title={it.tree.trash}
          submitLabel={it.tree.trash}
          danger
          onClose={() => setDialog(null)}
          onSubmit={() =>
            act(
              async () => {
                await trashPage(dialog.node.id, dialog.node.version);
              },
              it.tree.trashed(dialog.node.title),
              true,
            )
          }
        >
          <p>{it.tree.trashConfirm(dialog.node.title)}</p>
        </FormDialog>
      )}
    </section>
  );
}
