import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../../api/client";
import { fetchTrash, restorePage } from "../../api/pages";
import type { Page } from "../../api/types";
import { useSession } from "../../session/context";
import { it } from "../../text/it";
import { NoticeArea, type NoticeState } from "../../ui/Notice";

/** Data all'uso svizzero (10.10.2026), nel fuso del computer di chi guarda. */
function day(iso: string | null): string {
  const date = iso ? new Date(iso) : null;
  if (!date || Number.isNaN(date.getTime())) return "";
  const two = (n: number) => String(n).padStart(2, "0");
  return `${two(date.getDate())}.${two(date.getMonth() + 1)}.${date.getFullYear()}`;
}

export function TrashScreen() {
  const { reloadKey } = useSession();
  const [items, setItems] = useState<Page[] | null>(null);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [busy, setBusy] = useState(false);
  const latest = useRef(0);

  /** Le prime `count` pagine di risultati; vale solo l'ultima richiesta partita. */
  const reload = useCallback((count: number) => {
    const request = ++latest.current;
    return fetchTrash(count).then(
      (loaded) => {
        if (request !== latest.current) return;
        setItems(loaded.items);
        setTotal(loaded.total);
        setLoadError(null);
      },
      (error: unknown) => {
        if (request === latest.current) setLoadError(errorMessage(error));
      },
    );
  }, []);

  useEffect(() => {
    void reload(pages);
  }, [reload, reloadKey, pages]);

  async function restore(page: Page) {
    setBusy(true);
    try {
      await restorePage(page.id, page.version);
      setNotice({ kind: "success", text: it.trash.restored(page.title) });
    } catch (error) {
      setNotice({ kind: "error", text: errorMessage(error) });
    }
    await reload(pages);
    setBusy(false);
  }

  return (
    <section className="screen" aria-labelledby="trash-title">
      <div className="screen__head">
        <h1 id="trash-title" tabIndex={-1}>
          {it.trash.title}
        </h1>
      </div>
      <NoticeArea notice={notice} onClose={() => setNotice(null)} />
      {loadError && (
        <div className="notice notice--error" role="alert">
          <p>{loadError}</p>
          <button type="button" className="button button--small" onClick={() => void reload(pages)}>
            {it.retry}
          </button>
        </div>
      )}
      {items === null && !loadError && <p role="status">{it.loading}</p>}
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
                    disabled={busy}
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
      {items && items.length < total && (
        <button type="button" className="button" disabled={busy} onClick={() => setPages(pages + 1)}>
          {it.trash.more(total - items.length)}
        </button>
      )}
    </section>
  );
}
