import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../../api/client";
import { createEntry, fetchCollections, fetchEntries, restoreEntry, type CollectionInfo, type Entry, type EntryPage } from "../../api/entries";
import { Link } from "../../router/Link";
import { navigate, paths } from "../../router/router";
import { useSession } from "../../session/context";
import { en } from "../../text/entries";
import { ed } from "../../text/editor";
import { it } from "../../text/it";
import { FormDialog } from "../../ui/FormDialog";
import { NoticeArea, type NoticeState } from "../../ui/Notice";
import { formatZurich } from "../editor/schedule/siteTime";

type Tab = "list" | "trash";

function day(entry: Entry): string | null {
  // La data della notizia (sort_at) è un giorno: si mostra così com'è, senza fuso.
  if (!entry.sort_at) return null;
  const [year, month, date] = entry.sort_at.slice(0, 10).split("-");
  return `${date}.${month}.${year}`;
}

interface RowProps {
  entry: Entry;
  collection: string;
  trash: boolean;
  onRestore: (entry: Entry) => void;
}

function Row({ entry, collection, trash, onRestore }: RowProps) {
  const when = day(entry);
  return (
    <li>
      <div className="row">
        <div className="row__main">
          {trash ? (
            <strong className="row__title">{entry.title}</strong>
          ) : (
            <Link className="row__title" to={paths.entry(collection, entry.id)}>
              {entry.title}
            </Link>
          )}
          <span className="hint">{when ?? (entry.updated_at ? en.updated(formatZurich(entry.updated_at)) : "")}</span>
          <span className="row__badges">
            <span className={`badge badge--${entry.status}`}>{ed.status[entry.status]}</span>
            {entry.status === "published" && entry.has_draft && <span className="badge">{en.changes}</span>}
          </span>
        </div>
        {trash && (
          <div className="row__actions">
            <button type="button" className="button button--small" onClick={() => onRestore(entry)}>
              {en.restore}
            </button>
          </div>
        )}
      </div>
    </li>
  );
}

/** Le notizie di una raccolta (7b): elenco, cestino, nuova notizia. */
export function EntriesScreen({ collection }: { collection: string }) {
  const { site } = useSession();
  const label = site.collections.find((c) => c.key === collection)?.label ?? it.titles.entries;
  const [tab, setTab] = useState<Tab>("list");
  const [page, setPage] = useState(1);
  // Il risultato ricorda per quale scheda e pagina è arrivato: mai righe del cestino come se
  // fossero notizie (o il contrario) mentre arriva la risposta nuova.
  const [loaded, setLoaded] = useState<{ tab: Tab; page: number; result: EntryPage } | null>(null);
  const [info, setInfo] = useState<CollectionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const latest = useRef(0);

  const load = useCallback(() => {
    const request = ++latest.current;
    Promise.all([fetchEntries(collection, page, tab === "trash"), fetchCollections()]).then(
      ([entries, collections]) => {
        if (request !== latest.current) return;
        if (entries.items.length === 0 && page > 1) {
          setPage(page - 1); // l'ultima pagina si è svuotata (es. dopo un recupero)
          return;
        }
        setLoaded({ tab, page, result: entries });
        setInfo(collections.find((c) => c.key === collection) ?? null);
        setError(null);
      },
      (failure: unknown) => {
        if (request === latest.current) setError(errorMessage(failure));
      },
    );
  }, [collection, page, tab]);

  useEffect(() => {
    load();
  }, [load]);

  async function restore(entry: Entry) {
    try {
      await restoreEntry(entry.id, entry.version);
      setNotice({ kind: "success", text: en.restored(entry.title) });
      load();
    } catch (failure) {
      setNotice({ kind: "error", text: errorMessage(failure) });
    }
  }

  const found = loaded && loaded.tab === tab && loaded.page === page ? loaded.result : null;

  function closeNew() {
    setCreating(false);
    setTitle("");
  }

  function show(next: Tab) {
    setTab(next);
    setPage(1);
  }

  return (
    <section className="screen" aria-labelledby="entries-title">
      <div className="screen__head">
        <h1 id="entries-title" tabIndex={-1}>
          {label}
        </h1>
        <button type="button" className="button button--primary" onClick={() => setCreating(true)}>
          {en.newEntry}
        </button>
      </div>
      {info && !info.listing && (
        <p className="notice notice--info">
          {en.noListing} <Link to={paths.pages}>{en.toPages}</Link>
        </p>
      )}
      <div className="editor__toggle" role="group" aria-label={label}>
        <button type="button" className="button button--small" aria-pressed={tab === "list"} onClick={() => show("list")}>
          {en.tabs.list}
        </button>
        <button type="button" className="button button--small" aria-pressed={tab === "trash"} onClick={() => show("trash")}>
          {en.tabs.trash}
        </button>
      </div>
      <NoticeArea notice={notice} onClose={() => setNotice(null)} />
      {error && (
        <div className="notice notice--error" role="alert">
          <p>{error}</p>
          <button type="button" className="button button--small" onClick={load}>
            {it.retry}
          </button>
        </div>
      )}
      {!found && !error && <p role="status">{en.loading}</p>}
      {found && found.items.length === 0 && <p className="hint">{tab === "trash" ? en.trashEmpty : en.empty}</p>}
      {found && found.items.length > 0 && (
        <ul className="tree">
          {found.items.map((entry) => (
            <Row key={entry.id} entry={entry} collection={collection} trash={tab === "trash"} onRestore={(e) => void restore(e)} />
          ))}
        </ul>
      )}
      {found && found.pages > 1 && (
        <nav className="form__actions" aria-label={en.pageOf(page, found.pages)}>
          <button type="button" className="button button--small" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            {en.previous}
          </button>
          <span className="hint">{en.pageOf(page, found.pages)}</span>
          <button type="button" className="button button--small" disabled={page >= found.pages} onClick={() => setPage(page + 1)}>
            {en.next}
          </button>
        </nav>
      )}
      {creating && (
        <FormDialog
          title={en.newEntry}
          submitLabel={en.create}
          canSubmit={title.trim().length > 0}
          onClose={closeNew}
          onSubmit={async () => {
            const created = await createEntry(collection, title.trim());
            closeNew();
            await navigate(paths.entry(collection, created.id));
          }}
        >
          <div className="field">
            <label htmlFor="new-entry-title">{en.newTitle}</label>
            <input id="new-entry-title" maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} />
          </div>
        </FormDialog>
      )}
    </section>
  );
}
