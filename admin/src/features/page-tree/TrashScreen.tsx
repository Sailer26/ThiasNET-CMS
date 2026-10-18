import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "../../api/client";
import { fetchTrash, restorePage } from "../../api/pages";
import type { Page } from "../../api/types";
import { useSession } from "../../session/context";
import { it } from "../../text/it";
import { Notice, type NoticeState } from "../../ui/Notice";

/** Data all'uso svizzero (10.10.2026), uguale in ogni browser. */
function day(iso: string | null): string {
  const date = iso ? new Date(iso) : null;
  if (!date || Number.isNaN(date.getTime())) return "";
  const two = (n: number) => String(n).padStart(2, "0");
  return `${two(date.getDate())}.${two(date.getMonth() + 1)}.${date.getFullYear()}`;
}

export function TrashScreen() {
  const { reloadKey } = useSession();
  const [items, setItems] = useState<Page[] | null>(null);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  const reload = useCallback(
    () =>
      fetchTrash().then(setItems, (error: unknown) =>
        setNotice({ kind: "error", text: errorMessage(error) }),
      ),
    [],
  );

  useEffect(() => {
    void reload();
  }, [reload, reloadKey]);

  async function restore(page: Page) {
    setBusy(page.id);
    try {
      await restorePage(page.id, page.version);
      setNotice({ kind: "success", text: it.trash.restored(page.title) });
    } catch (error) {
      setNotice({ kind: "error", text: errorMessage(error) });
    } finally {
      setBusy(null);
    }
    await reload();
  }

  return (
    <section className="screen" aria-labelledby="trash-title">
      <div className="screen__head">
        <h1 id="trash-title">{it.trash.title}</h1>
      </div>
      {notice && <Notice {...notice} onClose={() => setNotice(null)} />}
      {items === null && !notice && <p role="status">{it.loading}</p>}
      {items?.length === 0 && <p className="empty">{it.trash.empty}</p>}
      {items && items.length > 0 && (
        <ul className="tree">
          {items.map((page) => (
            <li key={page.id} className="tree__item">
              <div className="row">
                <div className="row__main">
                  <span className="row__title">{page.title}</span>
                  <code className="row__path">{page.path}</code>
                  <span className="hint">
                    {it.trash.deletedAt} {day(page.deleted_at)}
                  </span>
                </div>
                <div className="row__actions">
                  <button
                    type="button"
                    className="button button--small"
                    disabled={busy !== null}
                    onClick={() => void restore(page)}
                  >
                    {it.trash.restore}
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
